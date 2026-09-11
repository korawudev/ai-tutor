"""Unit tests for gateway feynman API."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway.app.api.auth import get_user_id_dependency
from gateway.app.api.feynman import router
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
    with (
        patch("gateway.app.api.feynman.upsert_mastery", new=AsyncMock()),
        patch("gateway.app.api.feynman.record_daily_stats", new=AsyncMock()),
    ):
        yield


def _make_httpx_response(status_code=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data if json_data is not None else {}
    resp.text = str(json_data)
    return resp


def _make_httpx_client(mock_resp):
    """Create a MagicMock httpx.AsyncClient with proper async context manager."""
    instance = MagicMock()
    instance.__aenter__ = AsyncMock(return_value=instance)
    instance.__aexit__ = AsyncMock(return_value=False)
    instance.post = AsyncMock(return_value=mock_resp)
    instance.get = AsyncMock(return_value=mock_resp)
    return instance


class TestFeynmanEvaluate:
    """Tests for POST /api/feynman/evaluate"""

    def test_evaluate_no_auth(self):
        """No auth → 401."""
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/feynman/evaluate", params={"thread_id": str(uuid4())})
        assert resp.status_code == 401

    @patch("httpx.AsyncClient")
    def test_evaluate_no_conversation(self, mock_client_cls, client, mock_db):
        """No runs in thread → 400."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        resp = client.post(
            "/api/feynman/evaluate",
            params={"thread_id": str(uuid4())},
            headers={"Authorization": "Bearer dummy"},
        )
        assert resp.status_code == 400

    @patch("httpx.AsyncClient")
    def test_evaluate_success(self, mock_client_cls, client, mock_db, user_id):
        """Successful evaluation returns score + feedback."""
        from datetime import datetime

        from shared.models.thread import Run as RunORM
        from shared.models.thread import Thread as ThreadORM

        thread_id = uuid4()
        thread_obj = ThreadORM(
            id=thread_id,
            user_id=user_id,
            agent_type="feynman",
            status="active",
            state={},
            metadata_={},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        run_obj = RunORM(
            id=uuid4(),
            thread_id=thread_id,
            agent_type="feynman",
            status="completed",
            input={"input": "TCP三次握手是什么"},
            output={"response": "TCP三次握手是..."},
            created_at=datetime.utcnow(),
        )

        thread_result = MagicMock()
        thread_result.scalar_one_or_none.return_value = thread_obj

        runs_result = MagicMock()
        runs_result.scalars.return_value.all.return_value = [run_obj]

        mock_db.execute = AsyncMock(side_effect=[thread_result, runs_result])

        eval_response = {
            "choices": [
                {
                    "message": {
                        "content": '{"score": 75, "understanding": 80, "completeness": 70, '
                        '"clarity": 75,'
                        ' "strengths": ["正确描述了基本步骤"],'
                        ' "weaknesses": ["没有解释为什么需要三次握手"],'
                        ' "suggestions": ["建议复习TCP连接建立"]}',
                    },
                },
            ],
        }
        mock_resp = _make_httpx_response(200, eval_response)
        mock_resp.raise_for_status = MagicMock()
        mock_client_cls.return_value = _make_httpx_client(mock_resp)

        resp = client.post(
            "/api/feynman/evaluate",
            params={"thread_id": str(thread_id)},
            headers={"Authorization": "Bearer dummy"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "score" in data
        assert "strengths" in data
        assert "weaknesses" in data

    @patch("httpx.AsyncClient")
    def test_evaluate_llm_error_returns_fallback(self, mock_client_cls, client, mock_db, user_id):
        """LLM error returns fallback evaluation."""
        from datetime import datetime

        from shared.models.thread import Run as RunORM
        from shared.models.thread import Thread as ThreadORM

        thread_id = uuid4()
        thread_obj = ThreadORM(
            id=thread_id,
            user_id=user_id,
            agent_type="feynman",
            status="active",
            state={},
            metadata_={},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        run_obj = RunORM(
            id=uuid4(),
            thread_id=thread_id,
            agent_type="feynman",
            status="completed",
            input={"input": "TCP三次握手是什么"},
            output={"response": "TCP三次握手是..."},
            created_at=datetime.utcnow(),
        )

        def mock_execute(stmt):
            result = MagicMock()
            if "threads" in str(stmt) or "Thread" in str(stmt):
                result.scalar_one_or_none.return_value = thread_obj
            else:
                result.scalars.return_value.all.return_value = [run_obj]
            return result

        mock_db.execute = AsyncMock(side_effect=mock_execute)

        mock_resp = _make_httpx_response(500, {"error": "LLM timeout"})
        mock_client_cls.return_value = _make_httpx_client(mock_resp)

        resp = client.post(
            "/api/feynman/evaluate",
            params={"thread_id": str(thread_id)},
            headers={"Authorization": "Bearer dummy"},
        )
        assert resp.status_code == 500


class TestFeynmanAddToReview:
    """Tests for POST /api/feynman/add-to-review"""

    def test_add_review_no_auth(self):
        """No auth → 401."""
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/feynman/add-to-review",
            json={
                "thread_id": str(uuid4()),
                "score": 40,
                "review_items": [],
            },
        )
        assert resp.status_code == 401

    def test_add_review_success(self, client, mock_db, user_id):
        """Successful add-to-review writes ReviewSchedule rows directly."""
        from datetime import datetime

        from shared.models.thread import Thread as ThreadORM

        thread_id = uuid4()
        thread_obj = ThreadORM(
            id=thread_id,
            user_id=user_id,
            agent_type="feynman",
            status="active",
            state={},
            metadata_={},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = thread_obj
        mock_db.execute.return_value = mock_result

        resp = client.post(
            "/api/feynman/add-to-review",
            json={
                "thread_id": str(thread_id),
                "score": 45,
                "review_items": [
                    {
                        "topic": "TCP三次握手原因",
                        "answer": "为了保证双方都具备收发能力",
                        "source": "feynman",
                    },
                    {"topic": "网络延迟问题", "answer": "传播+排队+处理延迟", "source": "feynman"},
                ],
            },
            headers={"Authorization": "Bearer dummy"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["added"] == 2
        assert len(body["items"]) == 2

    def test_add_review_thread_not_found(self, client, mock_db):
        """Thread not found → 404."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        resp = client.post(
            "/api/feynman/add-to-review",
            json={
                "thread_id": str(uuid4()),
                "score": 40,
                "review_items": [{"topic": "test", "source": "feynman"}],
            },
            headers={"Authorization": "Bearer dummy"},
        )
        assert resp.status_code == 404

    def test_add_review_no_items(self, client, mock_db, user_id):
        """No review items → 400."""
        from datetime import datetime

        from shared.models.thread import Thread as ThreadORM

        thread_id = uuid4()
        thread_obj = ThreadORM(
            id=thread_id,
            user_id=user_id,
            agent_type="feynman",
            status="active",
            state={},
            metadata_={},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = thread_obj
        mock_db.execute.return_value = mock_result

        resp = client.post(
            "/api/feynman/add-to-review",
            json={"thread_id": str(thread_id), "score": 40, "review_items": []},
            headers={"Authorization": "Bearer dummy"},
        )
        assert resp.status_code == 400
