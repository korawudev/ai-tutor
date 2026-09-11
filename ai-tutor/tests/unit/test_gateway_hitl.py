"""Unit tests for gateway HITL API."""
import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient
from fastapi import FastAPI

from gateway.app.api.hitl import router
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


class TestResumeRun:
    def test_resume_no_auth(self):
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            f"/api/threads/{uuid4()}/runs/{uuid4()}/resume",
            json={"action": "continue", "input": {}}
        )
        assert resp.status_code == 401

    def test_resume_thread_not_found(self, client, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        resp = client.post(
            f"/api/threads/{uuid4()}/runs/{uuid4()}/resume",
            json={"action": "continue", "input": {}},
            headers={"Authorization": "Bearer dummy"}
        )
        assert resp.status_code == 404

    def test_resume_run_not_found(self, client, mock_db, user_id):
        thread_mock = MagicMock()
        thread_mock.id = uuid4()
        thread_mock.user_id = user_id

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.side_effect = [thread_mock, None]
        mock_db.execute.return_value = mock_result

        resp = client.post(
            f"/api/threads/{thread_mock.id}/runs/{uuid4()}/resume",
            json={"action": "continue", "input": {}},
            headers={"Authorization": "Bearer dummy"}
        )
        assert resp.status_code == 404

    def test_resume_wrong_status(self, client, mock_db, user_id):
        thread_mock = MagicMock()
        thread_mock.id = uuid4()
        thread_mock.user_id = user_id

        run_mock = MagicMock()
        run_mock.id = uuid4()
        run_mock.thread_id = thread_mock.id
        run_mock.status = "completed"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.side_effect = [thread_mock, run_mock]
        mock_db.execute.return_value = mock_result

        resp = client.post(
            f"/api/threads/{thread_mock.id}/runs/{run_mock.id}/resume",
            json={"action": "continue", "input": {}},
            headers={"Authorization": "Bearer dummy"}
        )
        assert resp.status_code == 400

    def test_resume_success(self, client, mock_db, user_id):
        from shared.models.thread import Thread as ThreadORM, Run as RunORM
        from datetime import datetime

        thread_id = uuid4()
        run_id = uuid4()
        thread_obj = ThreadORM(
            id=thread_id, user_id=user_id, agent_type="feynman",
            status="active", state={}, metadata_={},
            created_at=datetime.utcnow(), updated_at=datetime.utcnow()
        )
        run_obj = RunORM(
            id=run_id, thread_id=thread_id, agent_type="feynman",
            status="waiting_hitl", input={}, created_at=datetime.utcnow(),
            hitl_required=False, hitl_action=None, hitl_options=None,
            output=None, completed_at=None, error_message=None
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.side_effect = [thread_obj, run_obj]
        mock_db.execute.return_value = mock_result

        resp = client.post(
            f"/api/threads/{thread_id}/runs/{run_id}/resume",
            json={"action": "continue", "input": {"choice": "yes"}},
            headers={"Authorization": "Bearer dummy"}
        )
        assert resp.status_code == 200
        assert run_obj.status == "running"
