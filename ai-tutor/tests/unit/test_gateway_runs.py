"""Unit tests for gateway runs API."""
import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient
from fastapi import FastAPI

from gateway.app.api.runs import router
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


class TestCreateRun:
    def test_create_run_no_auth(self):
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            f"/api/threads/{uuid4()}/runs",
            json={"agent_type": "rag", "action": "start", "input": {}}
        )
        assert resp.status_code == 401

    def test_create_run_thread_not_found(self, client, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        resp = client.post(
            f"/api/threads/{uuid4()}/runs",
            json={"agent_type": "rag", "action": "start", "input": {}},
            headers={"Authorization": "Bearer dummy"}
        )
        assert resp.status_code == 404

    def test_create_run_success(self, client, mock_db, user_id):
        from shared.models.thread import Thread as ThreadORM
        from datetime import datetime

        thread_id = uuid4()
        thread_obj = ThreadORM(
            id=thread_id, user_id=user_id, agent_type="rag",
            status="active", state={}, metadata_={},
            created_at=datetime.utcnow(), updated_at=datetime.utcnow()
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = thread_obj
        mock_db.execute.return_value = mock_result

        async def fake_refresh(obj):
            if not getattr(obj, 'id', None):
                obj.id = uuid4()
            if not getattr(obj, 'created_at', None):
                obj.created_at = datetime.utcnow()
            if getattr(obj, 'hitl_required', None) is None:
                obj.hitl_required = False
            if getattr(obj, 'hitl_action', None) is None:
                obj.hitl_action = None
            if getattr(obj, 'hitl_options', None) is None:
                obj.hitl_options = None
            if getattr(obj, 'output', None) is None:
                obj.output = None
            if getattr(obj, 'completed_at', None) is None:
                obj.completed_at = None
            if getattr(obj, 'error_message', None) is None:
                obj.error_message = None
        mock_db.refresh = fake_refresh

        resp = client.post(
            f"/api/threads/{thread_id}/runs",
            json={"agent_type": "rag", "action": "start", "input": {}},
            headers={"Authorization": "Bearer dummy"}
        )
        assert resp.status_code == 201

    def test_create_run_feynman_returns_stream(self, client, mock_db, user_id):
        """Feynman mode returns StreamingResponse (200) instead of JSON (201)."""
        from shared.models.thread import Thread as ThreadORM
        from datetime import datetime

        thread_id = uuid4()
        thread_obj = ThreadORM(
            id=thread_id, user_id=user_id, agent_type="feynman",
            status="active", state={}, metadata_={},
            created_at=datetime.utcnow(), updated_at=datetime.utcnow()
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = thread_obj
        mock_db.execute.return_value = mock_result

        async def fake_refresh(obj):
            if not getattr(obj, 'id', None):
                obj.id = uuid4()
            if not getattr(obj, 'created_at', None):
                obj.created_at = datetime.utcnow()
            if getattr(obj, 'output', None) is None:
                obj.output = None
        mock_db.refresh = fake_refresh

        resp = client.post(
            f"/api/threads/{thread_id}/runs",
            json={"agent_type": "feynman", "action": "chat", "input": "TCP三次握手"},
            headers={"Authorization": "Bearer dummy"}
        )
        # SSE returns 200 with streaming content
        assert resp.status_code == 200


class TestGetRun:
    def test_get_run_no_auth(self):
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(f"/api/threads/{uuid4()}/runs/{uuid4()}")
        assert resp.status_code == 401

    def test_get_run_thread_not_found(self, client, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        resp = client.get(
            f"/api/threads/{uuid4()}/runs/{uuid4()}",
            headers={"Authorization": "Bearer dummy"}
        )
        assert resp.status_code == 404


class TestStreamEvents:
    def test_stream_no_auth(self):
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(f"/api/threads/{uuid4()}/runs/stream")
        assert resp.status_code == 401

    def test_stream_thread_not_found(self, client, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        resp = client.get(
            f"/api/threads/{uuid4()}/runs/stream",
            headers={"Authorization": "Bearer dummy"}
        )
        assert resp.status_code == 404


class TestListRuns:
    def test_list_runs_no_auth(self):
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(f"/api/threads/{uuid4()}/runs")
        assert resp.status_code == 401

    def test_list_runs_thread_not_found(self, client, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        resp = client.get(
            f"/api/threads/{uuid4()}/runs",
            headers={"Authorization": "Bearer dummy"}
        )
        assert resp.status_code == 404

    def test_list_runs_success(self, client, mock_db, user_id):
        """List-runs returns paginated completed runs (newest first)."""
        from shared.models.thread import Thread as ThreadORM, Run as RunORM
        from datetime import datetime

        thread_id = uuid4()
        thread_obj = ThreadORM(
            id=thread_id, user_id=user_id, agent_type="feynman",
            status="active", state={}, metadata_={},
            created_at=datetime.utcnow(), updated_at=datetime.utcnow()
        )
        run_obj = RunORM(
            id=uuid4(), thread_id=thread_id, agent_type="feynman",
            status="completed", input={"input": "你好"}, output={"response": "你好"},
            created_at=datetime.utcnow(),
            hitl_required=False, hitl_action=None, hitl_options=None,
            completed_at=datetime.utcnow(),
        )

        thread_result = MagicMock()
        thread_result.scalar_one_or_none.return_value = thread_obj
        runs_result = MagicMock()
        runs_result.scalars.return_value.all.return_value = [run_obj]
        mock_db.execute = AsyncMock(side_effect=[thread_result, runs_result])

        resp = client.get(
            f"/api/threads/{thread_id}/runs",
            params={"limit": 10, "offset": 0},
            headers={"Authorization": "Bearer dummy"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) == 1
        assert body[0]["output"]["response"] == "你好"
