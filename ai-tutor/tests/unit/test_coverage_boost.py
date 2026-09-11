"""Targeted tests to push coverage from 86% to 90%.
Covers success paths in gateway quiz/review/documents/feynman, jina_scraper,
quiz_service, and document_service that existing tests miss.
"""
import pytest
import sys
import os
import types
import json
from uuid import uuid4, UUID
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from fastapi import FastAPI


ROOT = os.path.join(os.path.dirname(__file__), "..", "..")


def _setup_knowledge_agent():
    """Setup module switching for knowledge-agent."""
    for k in list(sys.modules):
        if k == "app" or k.startswith("app."):
            del sys.modules[k]
    shared_pkg = types.ModuleType("shared")
    shared_pkg.__path__ = [os.path.join(ROOT, "shared")]
    sys.modules["shared"] = shared_pkg
    agent_app = os.path.join(ROOT, "knowledge-agent", "app")
    app_pkg = types.ModuleType("app")
    app_pkg.__path__ = [agent_app]
    sys.modules["app"] = app_pkg


@pytest.fixture(autouse=True)
def _patch_mastery_helpers():
    """Endpoint 测试只验证业务逻辑；掌握度/日统计落库走独立的 test_mastery.py。"""
    with patch("gateway.app.api.quiz.upsert_mastery", new=AsyncMock()), \
         patch("gateway.app.api.quiz.record_daily_stats", new=AsyncMock()), \
         patch("gateway.app.api.review.upsert_mastery", new=AsyncMock()), \
         patch("gateway.app.api.review.record_daily_stats", new=AsyncMock()), \
         patch("gateway.app.api.feynman.upsert_mastery", new=AsyncMock()), \
         patch("gateway.app.api.feynman.record_daily_stats", new=AsyncMock()):
        yield


# ---------------------------------------------------------------------------
# Jina Scraper  (jina_scraper.py — 21 uncovered lines)
# ---------------------------------------------------------------------------
class TestJinaScraper:
    """Covers scrape_with_jina: no API key, success with title, HTTP error, generic error."""

    def test_no_api_key(self):
        import asyncio
        _setup_knowledge_agent()
        import app.scrapers.jina_scraper as mod
        with patch.object(mod.settings, "JINA_API_KEY", ""):
            result = asyncio.run(
                mod.scrape_with_jina("https://example.com")
            )
        assert result.success is False
        assert "not configured" in result.error

    def test_success_with_title(self):
        import asyncio
        _setup_knowledge_agent()
        import app.scrapers.jina_scraper as mod
        mock_resp = MagicMock()
        mock_resp.text = "# My Title\nSome content"
        mock_resp.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)
        with patch.object(mod.settings, "JINA_API_KEY", "test-key"), \
             patch("httpx.AsyncClient", return_value=mock_client):
            result = asyncio.run(
                mod.scrape_with_jina("https://example.com")
            )
        assert result.success is True
        assert result.title == "My Title"
        assert "Some content" in result.content

    def test_success_no_title(self):
        import asyncio
        _setup_knowledge_agent()
        import app.scrapers.jina_scraper as mod
        mock_resp = MagicMock()
        mock_resp.text = "Just content, no title here"
        mock_resp.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)
        with patch.object(mod.settings, "JINA_API_KEY", "test-key"), \
             patch("httpx.AsyncClient", return_value=mock_client):
            result = asyncio.run(
                mod.scrape_with_jina("https://example.com")
            )
        assert result.success is True
        assert result.title is None

    def test_http_status_error(self):
        import asyncio
        _setup_knowledge_agent()
        import app.scrapers.jina_scraper as mod
        import httpx
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            message="rate limited", request=MagicMock(), response=mock_resp
        )
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)
        with patch.object(mod.settings, "JINA_API_KEY", "test-key"), \
             patch("httpx.AsyncClient", return_value=mock_client):
            result = asyncio.run(
                mod.scrape_with_jina("https://example.com")
            )
        assert result.success is False
        assert "429" in result.error

    def test_generic_exception(self):
        import asyncio
        _setup_knowledge_agent()
        import app.scrapers.jina_scraper as mod
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=ConnectionError("timeout"))
        with patch.object(mod.settings, "JINA_API_KEY", "test-key"), \
             patch("httpx.AsyncClient", return_value=mock_client):
            result = asyncio.run(
                mod.scrape_with_jina("https://example.com")
            )
        assert result.success is False
        assert "timeout" in result.error


# ---------------------------------------------------------------------------
# Gateway Quiz — success paths (quiz.py lines 79-107, 133-141, 154)
# ---------------------------------------------------------------------------
class TestGatewayQuizSubmitSuccess:
    """Quiz submit with matching answers + wrong answers + mastery change."""

    @pytest.fixture
    def client_and_deps(self, mock_db, user_id, valid_token):
        from gateway.app.api.quiz import router
        from gateway.app.api.auth import get_user_id_dependency
        from shared.database import get_db

        app = FastAPI()

        async def override_uid():
            return user_id
        async def override_db():
            yield mock_db

        app.dependency_overrides[get_user_id_dependency] = override_uid
        app.dependency_overrides[get_db] = override_db
        app.include_router(router)
        return TestClient(app, raise_server_exceptions=False), mock_db, user_id, valid_token

    def test_submit_quiz_success(self, client_and_deps):
        client, mock_db, user_id, valid_token = client_and_deps
        quiz_id = uuid4()
        questions = [
            {"id": "q1", "type": "choice", "question": "Q1", "options": {"A": "a", "B": "b"}, "answer": "A", "points": 20},
            {"id": "q2", "type": "choice", "question": "Q2", "options": {"A": "a", "B": "b"}, "answer": "B", "points": 20},
        ]
        quiz = MagicMock()
        quiz.id = quiz_id
        quiz.user_id = user_id
        quiz.questions = questions
        quiz.total_questions = 2

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = quiz
        mock_db.execute.return_value = mock_result

        resp = client.post(
            "/api/quiz/submit",
            json={"quiz_id": str(quiz_id), "answers": {"q1": "A", "q2": "B"}},
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["quiz_id"] == str(quiz_id)
        assert data["correct_count"] == 2
        assert data["total_questions"] == 2
        assert data["mastery_change"] == 10.0  # 100% correct → ≥0.9

    def test_submit_quiz_partial_correct(self, client_and_deps):
        client, mock_db, user_id, valid_token = client_and_deps
        quiz_id = uuid4()
        # 3 questions, 2 correct → 66.7% → <0.7 → mastery_change=0.0
        questions = [
            {"id": "q1", "type": "choice", "question": "Q1", "options": {"A": "a"}, "answer": "A", "points": 20},
            {"id": "q2", "type": "choice", "question": "Q2", "options": {"A": "a"}, "answer": "B", "points": 20},
            {"id": "q3", "type": "choice", "question": "Q3", "options": {"A": "a"}, "answer": "A", "points": 20},
        ]
        quiz = MagicMock()
        quiz.id = quiz_id
        quiz.user_id = user_id
        quiz.questions = questions
        quiz.total_questions = 3

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
            json={"quiz_id": str(quiz_id), "answers": {"q1": "A", "q2": "A", "q3": "A"}},
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["correct_count"] == 2
        # 2/3 = 0.667, <0.7 → mastery_change=5.0... wait no.
        # quiz.py: mastery_change = 10.0 if >=0.9 else 5.0 if >=0.7 else 0.0
        # 2/3=0.667 < 0.7 → mastery_change=0.0
        assert data["mastery_change"] == 0.0

    def test_submit_quiz_70_percent(self, client_and_deps):
        """7 out of 10 correct → 70% → mastery_change=5.0."""
        client, mock_db, user_id, valid_token = client_and_deps
        quiz_id = uuid4()
        questions = [
            {"id": f"q{i}", "type": "choice", "question": f"Q{i}",
             "options": {"A": "a"}, "answer": "A", "points": 10}
            for i in range(10)
        ]
        quiz = MagicMock()
        quiz.id = quiz_id
        quiz.user_id = user_id
        quiz.questions = questions
        quiz.total_questions = 10

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

        # 7 correct
        answers = {f"q{i}": "A" for i in range(10)}
        answers["q7"] = "wrong"
        answers["q8"] = "wrong"
        answers["q9"] = "wrong"

        resp = client.post(
            "/api/quiz/submit",
            json={"quiz_id": str(quiz_id), "answers": answers},
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["correct_count"] == 7
        assert data["mastery_change"] == 5.0  # 70% → ≥0.7

    def test_mark_wrong_mastered_success(self, client_and_deps):
        client, mock_db, user_id, valid_token = client_and_deps
        wq_id = uuid4()
        wq = MagicMock()
        wq.id = wq_id
        wq.mastered = False

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = wq
        mock_db.execute.return_value = mock_result

        resp = client.post(
            f"/api/quiz/wrong-book/{wq_id}/mastered",
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert resp.status_code == 200
        assert wq.mastered is True

    def test_mark_wrong_mastered_not_found(self, client_and_deps):
        client, mock_db, user_id, valid_token = client_and_deps
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        resp = client.post(
            f"/api/quiz/wrong-book/{uuid4()}/mastered",
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Gateway Review — success paths (review.py lines 72-114, 126-134)
# ---------------------------------------------------------------------------
class TestGatewayReviewSubmitSuccess:
    """Review submit with easy/good/hard/forgot results + stats with data."""

    @pytest.fixture
    def client_and_deps(self, mock_db, user_id, valid_token):
        from gateway.app.api.review import router
        from gateway.app.api.auth import get_user_id_dependency
        from shared.database import get_db

        app = FastAPI()

        async def override_uid():
            return user_id
        async def override_db():
            yield mock_db

        app.dependency_overrides[get_user_id_dependency] = override_uid
        app.dependency_overrides[get_db] = override_db
        app.include_router(router)
        return TestClient(app, raise_server_exceptions=False), mock_db, user_id, valid_token

    def _make_schedule(self, user_id, interval=2.0, ef=2.5, mastery=50.0, status="active"):
        s = MagicMock()
        s.id = uuid4()
        s.user_id = user_id
        s.chunk_id = uuid4()
        s.topic = "Python"
        s.answer = None
        s.source = "feynman"
        s.reason = None
        s.interval_days = interval
        s.ease_factor = ef
        s.mastery_score = mastery
        s.status = status
        s.review_count = 3
        s.next_review = datetime.utcnow() - timedelta(days=1)
        s.last_reviewed_at = datetime.utcnow() - timedelta(days=3)
        return s

    def test_submit_review_good(self, client_and_deps):
        client, mock_db, user_id, valid_token = client_and_deps
        schedule = self._make_schedule(user_id)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = schedule
        mock_db.execute.return_value = mock_result

        resp = client.post(
            "/api/review/submit",
            json={"schedule_id": str(schedule.id), "result": "good"},
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["old_interval"] == 2.0
        assert data["new_interval"] == 5.0  # 2.0 * 2.5
        assert data["mastery_score"] == 60.0  # 50 + 10

    def test_submit_review_easy(self, client_and_deps):
        client, mock_db, user_id, valid_token = client_and_deps
        schedule = self._make_schedule(user_id)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = schedule
        mock_db.execute.return_value = mock_result

        resp = client.post(
            "/api/review/submit",
            json={"schedule_id": str(schedule.id), "result": "easy"},
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["mastery_score"] == 65.0  # 50 + 15

    def test_submit_review_hard(self, client_and_deps):
        client, mock_db, user_id, valid_token = client_and_deps
        schedule = self._make_schedule(user_id)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = schedule
        mock_db.execute.return_value = mock_result

        resp = client.post(
            "/api/review/submit",
            json={"schedule_id": str(schedule.id), "result": "hard"},
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["mastery_score"] == 45.0  # 50 - 5

    def test_submit_review_forgot(self, client_and_deps):
        client, mock_db, user_id, valid_token = client_and_deps
        schedule = self._make_schedule(user_id)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = schedule
        mock_db.execute.return_value = mock_result

        resp = client.post(
            "/api/review/submit",
            json={"schedule_id": str(schedule.id), "result": "forgot"},
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["new_interval"] == 1.0
        assert data["mastery_score"] == 35.0  # 50 - 15

    def test_submit_review_mastery_cap(self, client_and_deps):
        """Mastery should cap at 100 → mastered status."""
        client, mock_db, user_id, valid_token = client_and_deps
        schedule = self._make_schedule(user_id, mastery=85.0)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = schedule
        mock_db.execute.return_value = mock_result

        resp = client.post(
            "/api/review/submit",
            json={"schedule_id": str(schedule.id), "result": "easy"},
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "mastered"
        assert data["mastery_score"] == 100.0  # 85 + 15 = 100 ≥ 90 → mastered

    def test_review_stats_with_data(self, client_and_deps):
        client, mock_db, user_id, valid_token = client_and_deps
        s1 = self._make_schedule(user_id, status="active")
        s1.next_review = datetime.utcnow() - timedelta(days=1)
        s2 = self._make_schedule(user_id, status="mastered")
        s2.next_review = datetime.utcnow() + timedelta(days=1)
        s3 = self._make_schedule(user_id, status="active")
        s3.next_review = datetime.utcnow() + timedelta(days=5)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [s1, s2, s3]
        mock_db.execute.return_value = mock_result

        resp = client.get(
            "/api/review/stats",
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert data["mastered"] == 1
        assert data["pending"] == 1  # s1 is overdue

    def test_pending_with_data(self, client_and_deps):
        client, mock_db, user_id, valid_token = client_and_deps
        s = self._make_schedule(user_id)
        s.next_review = datetime.utcnow() - timedelta(hours=1)

        # First call: pending query, second call: overdue count
        pending_result = MagicMock()
        pending_result.scalars.return_value.all.return_value = [s]
        overdue_result = MagicMock()
        overdue_result.scalars.return_value.all.return_value = [s]

        mock_db.execute.side_effect = [pending_result, overdue_result]

        resp = client.get(
            "/api/review/pending?limit=5",
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["pending_count"] == 1
        assert data["overdue_count"] == 1


# ---------------------------------------------------------------------------
# Gateway Feynman — success paths (feynman.py lines 56-65, 75-84)
# ---------------------------------------------------------------------------
class TestGatewayFeynmanSuccess:
    """Feynman explain and add-to-review success paths."""

    @pytest.fixture
    def client_and_deps(self, mock_db, user_id, valid_token):
        from gateway.app.api.feynman import router
        from gateway.app.api.auth import get_user_id_dependency
        from shared.database import get_db

        app = FastAPI()

        async def override_uid():
            return user_id
        async def override_db():
            yield mock_db

        app.dependency_overrides[get_user_id_dependency] = override_uid
        app.dependency_overrides[get_db] = override_db
        app.include_router(router)
        return TestClient(app, raise_server_exceptions=False), mock_db, user_id, valid_token

    def _mock_httpx(self, status_code=200, json_data=None):
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = json_data if json_data is not None else {}
        instance = MagicMock()
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        instance.post = AsyncMock(return_value=resp)
        return instance

    def test_explain_success(self, client_and_deps):
        """Evaluate endpoint success path."""
        client, mock_db, user_id, valid_token = client_and_deps
        mock_client = self._mock_httpx(200, {
            "choices": [{"message": {"content":
                '{"score": 75, "understanding": 80, "completeness": 70, "clarity": 75,'
                ' "strengths": [], "weaknesses": [], "suggestions": []}'
            }}]
        })
        mock_client.post.return_value.raise_for_status = MagicMock()

        # Set up mock_db for evaluate: thread query + runs query
        from shared.models.thread import Thread as ThreadORM, Run as RunORM
        from datetime import datetime

        thread_obj = ThreadORM(id=uuid4(), user_id=user_id, agent_type="feynman",
            status="active", state={}, metadata_={},
            created_at=datetime.utcnow(), updated_at=datetime.utcnow())
        run_obj = RunORM(id=uuid4(), thread_id=uuid4(), agent_type="feynman",
            status="completed", input={"input": "test"}, output={"response": "test"},
            created_at=datetime.utcnow())

        thread_result = MagicMock()
        thread_result.scalar_one_or_none.return_value = thread_obj
        runs_result = MagicMock()
        runs_result.scalars.return_value.all.return_value = [run_obj]
        mock_db.execute = AsyncMock(side_effect=[thread_result, runs_result])

        with patch("gateway.app.api.feynman.httpx.AsyncClient", return_value=mock_client):
            resp = client.post(
                "/api/feynman/evaluate",
                params={"thread_id": str(uuid4())},
                headers={"Authorization": f"Bearer {valid_token}"}
            )
        assert resp.status_code == 200
        assert resp.json()["score"] == 75

    def test_add_to_review_success(self, client_and_deps):
        """Add-to-review endpoint success path."""
        client, mock_db, user_id, valid_token = client_and_deps

        from shared.models.thread import Thread as ThreadORM
        from datetime import datetime

        thread_obj = ThreadORM(id=uuid4(), user_id=user_id, agent_type="feynman",
            status="active", state={}, metadata_={},
            created_at=datetime.utcnow(), updated_at=datetime.utcnow())
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = thread_obj
        mock_db.execute = AsyncMock(return_value=mock_result)

        resp = client.post(
            "/api/feynman/add-to-review",
            json={"thread_id": str(uuid4()), "score": 40,
                  "review_items": [{"topic": "TCP", "answer": "三次握手", "source": "feynman"}]},
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert resp.status_code == 200
        assert resp.json()["added"] == 1

    def test_explain_agent_unavailable(self, client_and_deps):
        """Evaluate endpoint when LLM returns error → 500."""
        client, mock_db, user_id, valid_token = client_and_deps
        mock_client = self._mock_httpx(500, {"error": "timeout"})
        mock_client.post.return_value.raise_for_status = MagicMock(side_effect=Exception("500"))

        from shared.models.thread import Thread as ThreadORM, Run as RunORM
        from datetime import datetime

        thread_obj = ThreadORM(id=uuid4(), user_id=user_id, agent_type="feynman",
            status="active", state={}, metadata_={},
            created_at=datetime.utcnow(), updated_at=datetime.utcnow())
        run_obj = RunORM(id=uuid4(), thread_id=uuid4(), agent_type="feynman",
            status="completed", input={"input": "test"}, output={"response": "test"},
            created_at=datetime.utcnow())

        thread_result = MagicMock()
        thread_result.scalar_one_or_none.return_value = thread_obj
        runs_result = MagicMock()
        runs_result.scalars.return_value.all.return_value = [run_obj]
        mock_db.execute = AsyncMock(side_effect=[thread_result, runs_result])

        with patch("gateway.app.api.feynman.httpx.AsyncClient", return_value=mock_client):
            resp = client.post(
                "/api/feynman/evaluate",
                params={"thread_id": str(uuid4())},
                headers={"Authorization": f"Bearer {valid_token}"}
            )
        assert resp.status_code == 500

    def test_add_to_review_no_items(self, client_and_deps):
        """Add-to-review with empty items → 400."""
        client, mock_db, user_id, valid_token = client_and_deps

        from shared.models.thread import Thread as ThreadORM
        from datetime import datetime

        thread_obj = ThreadORM(id=uuid4(), user_id=user_id, agent_type="feynman",
            status="active", state={}, metadata_={},
            created_at=datetime.utcnow(), updated_at=datetime.utcnow())
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = thread_obj
        mock_db.execute = AsyncMock(return_value=mock_result)

        resp = client.post(
            "/api/feynman/add-to-review",
            json={"thread_id": str(uuid4()), "score": 40, "review_items": []},
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Gateway Documents — success paths (documents.py lines 52-61, 75, 77, 86, 96-104, 113-120)
# ---------------------------------------------------------------------------
class TestGatewayDocumentsSuccess:
    """Documents proxy: create, list with filters, get, delete."""

    @pytest.fixture
    def client_and_deps(self, mock_db, user_id, valid_token):
        from gateway.app.api.documents import router
        from gateway.app.api.auth import get_user_id_dependency

        app = FastAPI()

        async def override_uid():
            return user_id

        app.dependency_overrides[get_user_id_dependency] = override_uid
        app.include_router(router)
        return TestClient(app, raise_server_exceptions=False), user_id, valid_token

    def _mock_httpx(self, status_code=200, json_data=None):
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = json_data if json_data is not None else {}
        resp.text = str(json_data)
        instance = MagicMock()
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        instance.post = AsyncMock(return_value=resp)
        instance.get = AsyncMock(return_value=resp)
        instance.delete = AsyncMock(return_value=resp)
        return instance

    def test_create_document_success(self, client_and_deps):
        client, user_id, valid_token = client_and_deps
        doc_id = uuid4()
        expected = {
            "id": str(doc_id), "title": "Test Doc", "source_type": "text",
            "source_url": None, "status": "completed", "tags": [],
            "chunk_count": 1, "created_at": datetime.utcnow().isoformat(),
            "processed_at": datetime.utcnow().isoformat()
        }
        mock_client = self._mock_httpx(201, expected)

        with patch("gateway.app.api.documents.httpx.AsyncClient", return_value=mock_client):
            resp = client.post(
                "/api/documents",
                json={"title": "Test Doc", "source_type": "text", "content": "hello"},
                headers={"Authorization": f"Bearer {valid_token}"}
            )
        assert resp.status_code == 201

    def test_create_document_error(self, client_and_deps):
        client, user_id, valid_token = client_and_deps
        mock_client = self._mock_httpx(500, {"detail": "error"})

        with patch("gateway.app.api.documents.httpx.AsyncClient", return_value=mock_client):
            resp = client.post(
                "/api/documents",
                json={"title": "Test", "source_type": "text", "content": "x"},
                headers={"Authorization": f"Bearer {valid_token}"}
            )
        assert resp.status_code == 500

    def test_list_documents_with_filters(self, client_and_deps):
        client, user_id, valid_token = client_and_deps
        mock_client = self._mock_httpx(200, [])

        with patch("gateway.app.api.documents.httpx.AsyncClient", return_value=mock_client):
            resp = client.get(
                "/api/documents?status=completed&tag=python&limit=5&offset=10",
                headers={"Authorization": f"Bearer {valid_token}"}
            )
        assert resp.status_code == 200

    def test_list_documents_error(self, client_and_deps):
        client, user_id, valid_token = client_and_deps
        mock_client = self._mock_httpx(500, {"detail": "err"})

        with patch("gateway.app.api.documents.httpx.AsyncClient", return_value=mock_client):
            resp = client.get(
                "/api/documents",
                headers={"Authorization": f"Bearer {valid_token}"}
            )
        assert resp.status_code == 500

    def test_get_document_success(self, client_and_deps):
        client, user_id, valid_token = client_and_deps
        doc_id = uuid4()
        mock_client = self._mock_httpx(200, {
            "id": str(doc_id), "title": "Doc", "source_type": "text",
            "source_url": None, "status": "completed", "tags": [],
            "chunk_count": 1, "created_at": datetime.utcnow().isoformat(),
            "processed_at": None
        })

        with patch("gateway.app.api.documents.httpx.AsyncClient", return_value=mock_client):
            resp = client.get(
                f"/api/documents/{doc_id}",
                headers={"Authorization": f"Bearer {valid_token}"}
            )
        assert resp.status_code == 200

    def test_get_document_error(self, client_and_deps):
        client, user_id, valid_token = client_and_deps
        mock_client = self._mock_httpx(404, {"detail": "not found"})

        with patch("gateway.app.api.documents.httpx.AsyncClient", return_value=mock_client):
            resp = client.get(
                f"/api/documents/{uuid4()}",
                headers={"Authorization": f"Bearer {valid_token}"}
            )
        assert resp.status_code == 404

    def test_delete_document_success(self, client_and_deps):
        client, user_id, valid_token = client_and_deps
        mock_client = self._mock_httpx(204, None)

        with patch("gateway.app.api.documents.httpx.AsyncClient", return_value=mock_client):
            resp = client.delete(
                f"/api/documents/delete/{uuid4()}",
                headers={"Authorization": f"Bearer {valid_token}"}
            )
        assert resp.status_code == 204

    def test_delete_document_error(self, client_and_deps):
        client, user_id, valid_token = client_and_deps
        mock_client = self._mock_httpx(500, {"detail": "err"})

        with patch("gateway.app.api.documents.httpx.AsyncClient", return_value=mock_client):
            resp = client.delete(
                f"/api/documents/delete/{uuid4()}",
                headers={"Authorization": f"Bearer {valid_token}"}
            )
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# Gateway Quiz — generate with LLM success (quiz.py lines 42-44)
# ---------------------------------------------------------------------------
class TestGatewayQuizGenerateSuccess:
    """Quiz generate with successful LLM call."""

    @pytest.fixture
    def client_and_deps(self, mock_db, user_id, valid_token):
        from gateway.app.api.quiz import router
        from gateway.app.api.auth import get_user_id_dependency
        from shared.database import get_db

        app = FastAPI()

        async def override_uid():
            return user_id
        async def override_db():
            yield mock_db

        app.dependency_overrides[get_user_id_dependency] = override_uid
        app.dependency_overrides[get_db] = override_db
        app.include_router(router)
        return TestClient(app, raise_server_exceptions=False), mock_db, user_id, valid_token

    @patch("gateway.app.api.quiz.llm_router")
    def test_generate_with_llm_success(self, mock_llm, client_and_deps):
        client, mock_db, user_id, valid_token = client_and_deps
        mock_llm.chat = AsyncMock(return_value={
            "content": json.dumps({
                "questions": [
                    {"id": "q1", "type": "choice", "question": "What is Python?",
                     "options": {"A": "Language", "B": "Snake"}, "answer": "A", "topic": "Python", "points": 20}
                ]
            })
        })

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result

        async def fake_refresh(obj):
            obj.id = uuid4()
            obj.created_at = datetime.utcnow()
        mock_db.refresh.side_effect = fake_refresh

        resp = client.post(
            "/api/quiz/generate",
            json={"scope": "topic", "topic": "Python", "question_count": 1},
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_questions"] == 1

    @patch("gateway.app.api.quiz.llm_router")
    def test_generate_with_topic_context(self, mock_llm, client_and_deps):
        """_get_knowledge_context with topic scope — covers lines 146-153."""
        client, mock_db, user_id, valid_token = client_and_deps
        mock_llm.chat = AsyncMock(return_value={
            "content": json.dumps({
                "questions": [
                    {"id": "q1", "type": "choice", "question": "Q?",
                     "options": {"A": "a"}, "answer": "A", "topic": "T", "points": 20}
                ]
            })
        })

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("Some knowledge about Python",)]

        def execute_side_effect(stmt, *a, **kw):
            from sqlalchemy.sql.selectable import Select
            if isinstance(stmt, Select) and ("quiz" in str(stmt) or "wrong_questions" in str(stmt)):
                r = MagicMock()
                r.fetchall.return_value = []
                return r
            return mock_result

        mock_db.execute = AsyncMock(side_effect=execute_side_effect)

        async def fake_refresh(obj):
            obj.id = uuid4()
            obj.created_at = datetime.utcnow()
        mock_db.refresh.side_effect = fake_refresh

        resp = client.post(
            "/api/quiz/generate",
            json={"scope": "topic", "topic": "Python"},
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert resp.status_code == 200
