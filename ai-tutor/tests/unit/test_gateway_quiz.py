"""Unit tests for gateway quiz API."""
import pytest
from uuid import uuid4
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from fastapi import FastAPI

from gateway.app.api.quiz import router
from gateway.app.api.auth import get_user_id_dependency
from shared.database import get_db


@pytest.fixture
def app(mock_db, user_id):
    app = FastAPI()

    async def override_get_user_id():
        return user_id

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_user_id_dependency] = override_get_user_id
    app.dependency_overrides[get_db] = override_get_db
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _patch_mastery_helpers():
    with patch("gateway.app.api.quiz.upsert_mastery", new=AsyncMock()), \
         patch("gateway.app.api.quiz.record_daily_stats", new=AsyncMock()):
        yield


class TestQuizGenerate:
    def test_generate_no_auth(self):
        """No auth → 401."""
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/quiz/generate", json={"scope": "topic"})
        assert resp.status_code == 401

    @patch("gateway.app.api.quiz.llm_router")
    def test_generate_fallback_on_llm_error(self, mock_llm, client, mock_db, valid_token):
        """LLM error → fallback questions."""
        mock_llm.chat.side_effect = Exception("LLM unavailable")

        # Mock _get_knowledge_context to return empty
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result

        # Mock db.refresh to populate quiz fields
        async def fake_refresh(obj):
            if not hasattr(obj, 'id') or obj.id is None:
                from uuid import uuid4 as _uuid
                from datetime import datetime
                obj.id = _uuid()
                obj.created_at = datetime.utcnow()
        mock_db.refresh.side_effect = fake_refresh

        resp = client.post(
            "/api/quiz/generate",
            json={"scope": "topic", "topic": "Python", "question_count": 2},
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert resp.status_code == 200


class TestQuizSubmit:
    def test_submit_no_auth(self):
        """No auth → 401."""
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/quiz/submit", json={"quiz_id": str(uuid4()), "answers": {}})
        assert resp.status_code == 401

    def test_submit_quiz_not_found(self, client, mock_db, valid_token):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        resp = client.post(
            "/api/quiz/submit",
            json={"quiz_id": str(uuid4()), "answers": {"q1": "A"}},
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert resp.status_code == 404

    def test_submit_success_includes_question_detail(self, client, mock_db, valid_token, user_id):
        """Submit success → result items include question text, options, explanation."""
        quiz = MagicMock()
        quiz.id = uuid4()
        quiz.user_id = user_id
        quiz.questions = [
            {
                "id": "q1", "type": "choice",
                "question": "以下哪个是 Python 的列表？",
                "options": {"A": "[]", "B": "{}", "C": "()", "D": "set()"},
                "answer": "A", "explanation": "Python 中列表字面量是 []。",
                "topic": "Python", "points": 20,
            },
            {
                "id": "q2", "type": "short_answer",
                "question": "Python 中如何定义函数？",
                "answer": "def", "explanation": "Python 使用 def 关键字定义函数。",
                "topic": "Python", "points": 20,
            },
        ]
        quiz.total_questions = 2
        quiz.status = "pending"

        added_objs = []
        mock_db.add.side_effect = lambda obj: added_objs.append(obj)
        async def fake_flush():
            for obj in added_objs:
                if hasattr(obj, "id") and getattr(obj, "id") is None:
                    obj.id = uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = quiz
        mock_db.execute.return_value = mock_result
        mock_db.flush.side_effect = fake_flush

        resp = client.post(
            "/api/quiz/submit",
            json={"quiz_id": str(quiz.id), "answers": {"q1": "B", "q2": "def"}},
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["results"][0]["question"] == "以下哪个是 Python 的列表？"
        assert body["results"][0]["options"] == {"A": "[]", "B": "{}", "C": "()", "D": "set()"}
        assert body["results"][0]["explanation"] == "Python 中列表字面量是 []。"
        assert body["results"][0]["correct"] is False
        assert body["results"][1]["correct"] is True
        assert body["wrong_questions"][0]["question"]["question"] == "以下哪个是 Python 的列表？"


class TestWrongBook:
    def test_wrong_book_no_auth(self):
        """No auth → 401."""
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/quiz/wrong-book")
        assert resp.status_code == 401

    def test_wrong_book_empty(self, client, mock_db, valid_token):
        from sqlalchemy.sql.selectable import Select
        def side_effect(stmt, *a, **kw):
            if isinstance(stmt, Select) and "review_schedule" in str(stmt):
                r2 = MagicMock()
                r2.fetchall.return_value = []
                return r2
            r1 = MagicMock()
            r1.scalars.return_value.all.return_value = []
            return r1
        mock_db.execute.side_effect = side_effect

        resp = client.get(
            "/api/quiz/wrong-book",
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_wrong_book_in_review_flag(self, client, mock_db, valid_token, user_id):
        from shared.models import WrongQuestion, ReviewSchedule
        from sqlalchemy.sql.selectable import Select
        wq = WrongQuestion(
            id=uuid4(),
            question={"question": "Q1", "topic": "Topic1"},
            correct_answer="A", explanation="E1", mastered=False,
            review_count=0, created_at=datetime.utcnow(),
        )
        def side_effect(stmt, *a, **kw):
            if isinstance(stmt, Select) and "review_schedule" in str(stmt):
                r2 = MagicMock()
                r2.fetchall.return_value = [("Q1",)]
                return r2
            r1 = MagicMock()
            r1.scalars.return_value.all.return_value = [wq]
            return r1
        mock_db.execute.side_effect = side_effect

        resp = client.get(
            "/api/quiz/wrong-book",
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["in_review"] is True

    def test_wrong_book_in_review_false(self, client, mock_db, valid_token):
        from shared.models import WrongQuestion
        from sqlalchemy.sql.selectable import Select
        wq = WrongQuestion(
            id=uuid4(),
            question={"question": "Q1", "topic": "Topic1"},
            correct_answer="A", explanation="E1", mastered=False,
            review_count=0, created_at=datetime.utcnow(),
        )
        def side_effect(stmt, *a, **kw):
            if isinstance(stmt, Select) and "review_schedule" in str(stmt):
                r2 = MagicMock()
                r2.fetchall.return_value = [("Topic1",)]
                return r2
            r1 = MagicMock()
            r1.scalars.return_value.all.return_value = [wq]
            return r1
        mock_db.execute.side_effect = side_effect

        resp = client.get(
            "/api/quiz/wrong-book",
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert resp.status_code == 200
        assert resp.json()[0]["in_review"] is False

    def test_mark_mastered_no_auth(self):
        """No auth → 401."""
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(f"/api/quiz/wrong-book/{uuid4()}/mastered")
        assert resp.status_code == 401


class TestSuggestedReviews:
    def _setup_quiz(self, user_id, questions, mock_db, scope="topic"):
        quiz = MagicMock()
        quiz.id = uuid4()
        quiz.user_id = user_id
        quiz.scope = scope
        quiz.questions = questions
        quiz.total_questions = len(questions)
        quiz.status = "pending"
        added_objs = []
        mock_db.add.side_effect = lambda obj: added_objs.append(obj)
        async def fake_flush():
            for obj in added_objs:
                if hasattr(obj, "id") and getattr(obj, "id") is None:
                    obj.id = uuid4()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = quiz
        mock_db.execute.return_value = mock_result
        mock_db.flush.side_effect = fake_flush
        return quiz, added_objs

    QUESTIONS = [
        {"id": "q1", "type": "choice", "question": "Q1", "options": {"A": "a", "B": "b"}, "answer": "A", "explanation": "E1", "topic": "T", "points": 20},
        {"id": "q2", "type": "choice", "question": "Q2", "options": {"A": "a", "B": "b"}, "answer": "B", "explanation": "E2", "topic": "T", "points": 20},
    ]

    def test_submit_wrong_returns_suggested_reviews(self, client, mock_db, valid_token, user_id):
        quiz, _ = self._setup_quiz(user_id, self.QUESTIONS, mock_db)
        resp = client.post(
            "/api/quiz/submit",
            json={"quiz_id": str(quiz.id), "answers": {"q1": "B", "q2": "B"}},
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["suggested_reviews"]) == 1
        sr = body["suggested_reviews"][0]
        assert sr["correct_answer"] == "A"
        assert sr["explanation"] == "E1"
        assert sr["question"]["question"] == "Q1"
        assert "wrong_id" in sr

    def test_submit_all_correct_no_suggestions(self, client, mock_db, valid_token, user_id):
        quiz, _ = self._setup_quiz(user_id, self.QUESTIONS, mock_db)
        resp = client.post(
            "/api/quiz/submit",
            json={"quiz_id": str(quiz.id), "answers": {"q1": "A", "q2": "B"}},
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert resp.status_code == 200
        assert resp.json()["suggested_reviews"] == []


class TestWrongReview:
    def _wrong(self, question_text="Q1", answer="A", explanation="E1", topic="T"):
        from shared.models import WrongQuestion
        return WrongQuestion(
            question={"id": "q1", "type": "choice", "question": question_text, "options": {"A": "a", "B": "b"}, "answer": answer, "explanation": explanation, "topic": topic, "points": 20},
            user_answer="B", correct_answer=answer, explanation=explanation, error_type="choice", mastered=False, review_count=0,
        )

    def test_generate_wrong_review_no_auth(self):
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/quiz/generate", json={"scope": "wrong_review"})
        assert resp.status_code == 401

    def test_generate_from_wrong_questions(self, client, mock_db, valid_token, user_id):
        from unittest.mock import patch
        wqs = [self._wrong(question_text=f"Q{i}", answer="A") for i in range(1, 3)]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = wqs
        mock_db.execute.return_value = mock_result
        async def fake_refresh(obj):
            if getattr(obj, "id", None) is None:
                obj.id = uuid4()
            if getattr(obj, "created_at", None) is None:
                obj.created_at = datetime.utcnow()
        mock_db.refresh.side_effect = fake_refresh

        with patch("gateway.app.api.quiz.llm_router") as mock_llm:
            resp = client.post(
                "/api/quiz/generate",
                json={"scope": "wrong_review", "question_count": 5},
                headers={"Authorization": f"Bearer {valid_token}"}
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_questions"] == 2
        assert mock_llm.chat.call_count == 0
        assert body["questions"][0]["question"] == "Q1"
        assert body["questions"][0]["id"] == "wq1"
        assert body["questions"][1]["id"] == "wq2"

    def test_generate_no_wrong_questions_400(self, client, mock_db, valid_token):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        resp = client.post(
            "/api/quiz/generate",
            json={"scope": "wrong_review", "question_count": 5},
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert resp.status_code == 400
        assert "暂无错题" in resp.json()["detail"]

    def test_submit_wrong_review_correct_marks_mastered(self, client, mock_db, valid_token, user_id):
        wq = self._wrong(question_text="Q1", answer="A", explanation="E1")
        questions = [{"id": "wq1", "type": "choice", "question": "Q1", "options": {"A": "a", "B": "b"}, "answer": "A", "explanation": "E1", "topic": "T", "points": 20}]
        quiz = MagicMock()
        quiz.id = uuid4()
        quiz.user_id = user_id
        quiz.scope = "wrong_review"
        quiz.questions = questions
        quiz.total_questions = 1
        quiz.status = "pending"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = quiz
        mock_result.scalars.return_value.all.return_value = [wq]
        mock_db.execute.return_value = mock_result

        resp = client.post(
            "/api/quiz/submit",
            json={"quiz_id": str(quiz.id), "answers": {"wq1": "A"}},
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert resp.status_code == 200
        assert wq.mastered is True
        assert wq.review_count == 1
        assert resp.json()["suggested_reviews"] == []

    def test_submit_wrong_review_wrong_counts_no_duplicate(self, client, mock_db, valid_token, user_id):
        wq = self._wrong(question_text="Q1", answer="A", explanation="E1")
        questions = [{"id": "wq1", "type": "choice", "question": "Q1", "options": {"A": "a", "B": "b"}, "answer": "A", "explanation": "E1", "topic": "T", "points": 20}]
        quiz = MagicMock()
        quiz.id = uuid4()
        quiz.user_id = user_id
        quiz.scope = "wrong_review"
        quiz.questions = questions
        quiz.total_questions = 1
        quiz.status = "pending"

        added_objs = []
        mock_db.add.side_effect = lambda obj: added_objs.append(obj)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = quiz
        mock_result.scalars.return_value.all.return_value = [wq]
        mock_db.execute.return_value = mock_result
        mock_db.flush = AsyncMock()

        resp = client.post(
            "/api/quiz/submit",
            json={"quiz_id": str(quiz.id), "answers": {"wq1": "B"}},
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert resp.status_code == 200
        assert wq.mastered is False
        assert wq.review_count == 1
        assert added_objs == []
        body = resp.json()
        assert body["wrong_questions"][0]["id"] == str(wq.id)


class TestAddToReview:
    def test_add_to_review_no_auth(self):
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/quiz/wrong-book/add-to-review", json={"wrong_ids": [str(uuid4())]})
        assert resp.status_code == 401

    def test_add_to_review_empty_ids_400(self, client, mock_db, valid_token):
        resp = client.post(
            "/api/quiz/wrong-book/add-to-review",
            json={"wrong_ids": []},
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert resp.status_code == 400

    def test_add_to_review_creates_schedules(self, client, mock_db, valid_token, user_id):
        from shared.models import WrongQuestion, ReviewSchedule
        wqs = [
            WrongQuestion(id=uuid4(), question={"question": "Q1题干", "type": "choice", "options": {"A": "Auto-streaming", "B": "Batch"}, "topic": "Topic1", "answer": "A"}, correct_answer="A", explanation="E1", mastered=False),
            WrongQuestion(id=uuid4(), question={"question": "Q2题干", "type": "short_answer", "topic": "Topic2", "answer": "B"}, correct_answer="B", explanation="E2", mastered=False),
        ]
        created_schedules = []
        mock_db.add.side_effect = lambda obj: created_schedules.append(obj) if isinstance(obj, ReviewSchedule) else None
        async def fake_flush():
            for obj in created_schedules:
                if getattr(obj, "id", None) is None:
                    obj.id = uuid4()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = wqs
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        mock_db.flush.side_effect = fake_flush

        resp = client.post(
            "/api/quiz/wrong-book/add-to-review",
            json={"wrong_ids": [str(w.id) for w in wqs]},
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["added"] == 2
        assert body["skipped"] == 0
        assert len(body["items"]) == 2
        assert len(created_schedules) == 2
        assert all(s.source == "quiz" for s in created_schedules)
        assert all(s.reason == "wrong" for s in created_schedules)
        assert all(float(s.interval_days) == 1.0 for s in created_schedules)
        assert all(float(s.mastery_score) == 10.0 for s in created_schedules)
        # topic = 题干, answer = 正确答案(选项内容) + 解析
        assert created_schedules[0].topic == "Q1题干"
        assert created_schedules[1].topic == "Q2题干"
        # 选择题: 答案字母映射到选项具体内容
        assert created_schedules[0].answer == "正确答案: Auto-streaming\n解析: E1"
        # 简答题: 无 options, 直接用答案本身
        assert created_schedules[1].answer == "正确答案: B\n解析: E2"

    def test_add_to_review_skips_duplicates(self, client, mock_db, valid_token, user_id):
        from shared.models import WrongQuestion, ReviewSchedule
        wqs = [WrongQuestion(id=uuid4(), question={"question": "Q1题干", "topic": "Topic1"}, correct_answer="A", explanation="E1", mastered=False)]
        existing = ReviewSchedule(user_id=user_id, topic="Q1题干", source="quiz", status="active")
        created_schedules = []
        mock_db.add.side_effect = lambda obj: created_schedules.append(obj) if isinstance(obj, ReviewSchedule) else None

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = wqs
        mock_result.scalar_one_or_none.return_value = existing
        mock_db.execute.return_value = mock_result

        resp = client.post(
            "/api/quiz/wrong-book/add-to-review",
            json={"wrong_ids": [str(w.id) for w in wqs]},
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["added"] == 0
        assert body["skipped"] == 1
        assert created_schedules == []
