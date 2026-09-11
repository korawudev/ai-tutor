"""Integration tests simulating full user flows with mocked DB.
Tests gateway routing, auth, and endpoint logic end-to-end.
"""
import json
import pytest
from uuid import uuid4
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from fastapi import FastAPI

from gateway.app.api import (
    auth_router, documents_router, quiz_router,
    review_router, threads_router, runs_router,
    hitl_router, progress_router, feynman_router,
)
from gateway.app.api.auth import get_user_id_dependency
from shared.database import get_db
from shared.utils import create_access_token


@pytest.fixture
def mock_db():
    db = AsyncMock()

    async def fake_refresh(obj):
        if not hasattr(obj, "id") or obj.id is None:
            obj.id = uuid4()
        if not hasattr(obj, "created_at") or obj.created_at is None:
            obj.created_at = datetime.utcnow()

    db.refresh.side_effect = fake_refresh
    return db


@pytest.fixture
def client(mock_db):
    app = FastAPI()
    for r in [auth_router, documents_router, quiz_router, review_router,
              threads_router, runs_router, hitl_router, progress_router, feynman_router]:
        app.include_router(r)

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db
    return TestClient(app, raise_server_exceptions=False)


class TestRegisterThenLogin:
    def test_register_and_login(self, client, mock_db):
        mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

        reg_resp = client.post("/api/auth/register", json={
            "username": "flowuser", "email": "flow@example.com", "password": "flowpass123"
        })
        assert reg_resp.status_code == 201
        assert "access_token" in reg_resp.json()

        from shared.utils import hash_password
        fake_user = MagicMock()
        fake_user.email = "flow@example.com"
        fake_user.username = "flowuser"
        fake_user.hashed_password = hash_password("flowpass123")
        fake_user.id = uuid4()
        fake_user.created_at = datetime.utcnow()
        fake_user.avatar_url = None
        mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=fake_user))

        login_resp = client.post("/api/auth/login", json={
            "email": "flow@example.com", "password": "flowpass123"
        })
        assert login_resp.status_code == 200
        assert "access_token" in login_resp.json()

    def test_register_duplicate_email(self, client, mock_db):
        from shared.models import User
        existing = MagicMock(spec=User)
        existing.email = "dup@example.com"
        mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=existing))

        resp = client.post("/api/auth/register", json={
            "username": "dupuser", "email": "dup@example.com", "password": "pass123"
        })
        assert resp.status_code == 400


class TestImportThenQuizFlow:
    def test_import_then_generate_quiz(self, client, mock_db):
        user_id = uuid4()
        token = create_access_token(user_id)
        headers = {"Authorization": f"Bearer {token}"}

        mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

        with patch("gateway.app.api.documents.httpx.AsyncClient") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "batch_id": str(uuid4()), "total": 1, "completed": 1,
                "failed": 0, "skipped": 0, "documents": [], "duplicates": []
            }
            inst = MagicMock()
            inst.__aenter__ = AsyncMock(return_value=inst)
            inst.__aexit__ = AsyncMock(return_value=False)
            inst.post = AsyncMock(return_value=mock_resp)
            mock_httpx.return_value = inst

            import_resp = client.post("/api/documents/import", json={
                "sources": [{"type": "url", "value": "https://example.com/doc"}]
            }, headers=headers)
            assert import_resp.status_code == 200

        with patch("gateway.app.api.quiz.llm_router") as mock_llm:
            mock_llm.chat = AsyncMock(return_value={
                "content": json.dumps({
                    "questions": [
                        {"id": "q1", "type": "choice", "question": "What is Python?",
                         "options": {"A": "Language", "B": "Snake"},
                         "answer": "A", "topic": "Python", "points": 20}
                    ]
                })
            })
            quiz_resp = client.post("/api/quiz/generate", json={
                "scope": "topic", "topic": "Python", "question_count": 1
            }, headers=headers)
            assert quiz_resp.status_code == 200
            assert quiz_resp.json()["total_questions"] == 1


class TestQuizSubmitThenWrongBook:
    def test_wrong_answer_flows_to_wrong_book(self, client, mock_db):
        user_id = uuid4()
        token = create_access_token(user_id)
        headers = {"Authorization": f"Bearer {token}"}

        quiz_id = uuid4()
        quiz = MagicMock()
        quiz.id = quiz_id
        quiz.user_id = user_id
        quiz.questions = [
            {"id": "q1", "type": "choice", "question": "Q?",
             "options": {"A": "a", "B": "b"}, "answer": "A", "points": 20}
        ]
        quiz.total_questions = 1

        mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=quiz))

        submit_resp = client.post("/api/quiz/submit", json={
            "quiz_id": str(quiz_id), "answers": {"q1": "B"}
        }, headers=headers)
        assert submit_resp.status_code == 200
        result = submit_resp.json()
        assert result["correct_count"] == 0
        assert len(result["wrong_questions"]) == 1

        mock_db.execute.return_value = MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
        wrong_book_resp = client.get("/api/quiz/wrong-book", headers=headers)
        assert wrong_book_resp.status_code == 200

    def test_mastered_wrong_question(self, client, mock_db):
        user_id = uuid4()
        token = create_access_token(user_id)
        headers = {"Authorization": f"Bearer {token}"}

        wq = MagicMock()
        wq.id = uuid4()
        wq.mastered = False
        mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=wq))

        resp = client.post(f"/api/quiz/wrong-book/{wq.id}/mastered", headers=headers)
        assert resp.status_code == 200
        assert wq.mastered is True


class TestReviewFlow:
    def test_submit_review_easy(self, client, mock_db):
        user_id = uuid4()
        token = create_access_token(user_id)
        headers = {"Authorization": f"Bearer {token}"}

        s = MagicMock()
        s.id = uuid4()
        s.user_id = user_id
        s.chunk_id = uuid4()
        s.topic = "Python"
        s.source = "feynman"
        s.reason = None
        s.interval_days = 2.0
        s.ease_factor = 2.5
        s.mastery_score = 50.0
        s.status = "active"
        s.review_count = 3
        s.next_review = datetime.utcnow() - timedelta(days=1)
        s.last_reviewed_at = datetime.utcnow() - timedelta(days=3)

        mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=s))

        resp = client.post("/api/review/submit", json={
            "schedule_id": str(s.id), "result": "easy"
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["mastery_score"] == 65.0
        assert data["status"] == "active"

    def test_submit_review_forgot_resets(self, client, mock_db):
        user_id = uuid4()
        token = create_access_token(user_id)
        headers = {"Authorization": f"Bearer {token}"}

        s = MagicMock()
        s.id = uuid4()
        s.user_id = user_id
        s.chunk_id = uuid4()
        s.topic = "Algo"
        s.source = "quiz"
        s.reason = "wrong"
        s.interval_days = 10.0
        s.ease_factor = 2.5
        s.mastery_score = 70.0
        s.status = "active"
        s.review_count = 5
        s.next_review = datetime.utcnow() - timedelta(days=5)
        s.last_reviewed_at = datetime.utcnow() - timedelta(days=10)

        mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=s))

        resp = client.post("/api/review/submit", json={
            "schedule_id": str(s.id), "result": "forgot"
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["new_interval"] == 1.0
        assert data["mastery_score"] == 55.0

    def test_review_stats_and_pending(self, client, mock_db):
        user_id = uuid4()
        token = create_access_token(user_id)
        headers = {"Authorization": f"Bearer {token}"}

        s = MagicMock()
        s.status = "active"
        s.next_review = datetime.utcnow() - timedelta(hours=1)
        s.chunk_id = uuid4()
        s.topic = "Python"
        s.mastery_score = 50.0
        s.interval_days = 2.0
        s.review_count = 1
        s.source = "feynman"
        s.reason = None
        s.id = uuid4()

        stats_result = MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[s]))))
        pending_result = MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[s]))))
        overdue_result = MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[s]))))

        mock_db.execute.side_effect = [stats_result, pending_result, overdue_result]

        stats_resp = client.get("/api/review/stats", headers=headers)
        assert stats_resp.status_code == 200
        assert "total" in stats_resp.json()
        assert stats_resp.json()["total"] == 1

        pending_resp = client.get("/api/review/pending", headers=headers)
        assert pending_resp.status_code == 200
        assert "pending_count" in pending_resp.json()


class TestFeynmanProxyFlow:
    def test_start_and_explain(self, client, mock_db):
        user_id = uuid4()
        token = create_access_token(user_id)
        headers = {"Authorization": f"Bearer {token}"}

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"thread_id": "t1", "state": "asking"}
        inst = MagicMock()
        inst.__aenter__ = AsyncMock(return_value=inst)
        inst.__aexit__ = AsyncMock(return_value=False)
        inst.post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=inst):
            start_resp = client.post("/api/feynman/start",
                                     json={"topic": "Python classes"}, headers=headers)
            assert start_resp.status_code == 200

        mock_resp.json.return_value = {"state": "evaluating", "feedback": "good"}
        with patch("httpx.AsyncClient", return_value=inst):
            explain_resp = client.post("/api/feynman/explain",
                                       json={"thread_id": "t1", "explanation": "A class is..."},
                                       headers=headers)
            assert explain_resp.status_code == 200
            assert explain_resp.json()["state"] == "evaluating"


class TestThreadLifecycle:
    def test_create_thread(self, client, mock_db):
        user_id = uuid4()
        token = create_access_token(user_id)
        headers = {"Authorization": f"Bearer {token}"}

        async def fake_refresh(obj):
            if not hasattr(obj, "id") or obj.id is None:
                obj.id = uuid4()
            if not hasattr(obj, "created_at") or obj.created_at is None:
                obj.created_at = datetime.utcnow()
            if not hasattr(obj, "status") or obj.status is None:
                obj.status = "active"
            if not hasattr(obj, "state") or obj.state is None:
                obj.state = {}
            if not hasattr(obj, "metadata_") or obj.metadata_ is None:
                obj.metadata_ = {}

        mock_db.refresh.side_effect = fake_refresh

        t = MagicMock()
        t.id = uuid4()
        t.agent_type = "quiz"
        t.status = "active"
        t.state = {}
        t.metadata_ = {}
        t.created_at = datetime.utcnow()

        mock_db.execute.return_value = MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[t])))
        )

        create_resp = client.post("/api/threads", json={"agent_type": "quiz"}, headers=headers)
        assert create_resp.status_code == 201

        list_resp = client.get("/api/threads", headers=headers)
        assert list_resp.status_code == 200
