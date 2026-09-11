"""Unit tests for gateway threads API."""
import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient
from fastapi import FastAPI

from gateway.app.api.threads import router
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


class TestCreateThread:
    def test_create_thread_no_auth(self):
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/threads", json={"agent_type": "feynman"})
        assert resp.status_code == 401

    def test_create_thread_success(self, client, mock_db, user_id):
        async def fake_refresh(obj):
            from datetime import datetime
            if not getattr(obj, 'id', None):
                obj.id = uuid4()
            if not getattr(obj, 'created_at', None):
                obj.created_at = datetime.utcnow()
            if not getattr(obj, 'status', None):
                obj.status = 'active'
        mock_db.refresh = fake_refresh

        resp = client.post(
            "/api/threads",
            json={"agent_type": "feynman"},
            headers={"Authorization": "Bearer dummy"}
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["agent_type"] == "feynman"
        assert data["status"] == "active"


class TestListThreads:
    def test_list_threads_no_auth(self):
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/threads")
        assert resp.status_code == 401

    def test_list_threads_empty(self, client, mock_db):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        resp = client.get(
            "/api/threads",
            headers={"Authorization": "Bearer dummy"}
        )
        assert resp.status_code == 200
        assert resp.json() == []


class TestGetThread:
    def test_get_thread_no_auth(self):
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(f"/api/threads/{uuid4()}")
        assert resp.status_code == 401

    def test_get_thread_not_found(self, client, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        resp = client.get(
            f"/api/threads/{uuid4()}",
            headers={"Authorization": "Bearer dummy"}
        )
        assert resp.status_code == 404


class TestDeleteThread:
    def test_delete_thread_no_auth(self):
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.delete(f"/api/threads/{uuid4()}")
        assert resp.status_code == 401

    def test_delete_thread_not_found(self, client, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        resp = client.delete(
            f"/api/threads/{uuid4()}",
            headers={"Authorization": "Bearer dummy"}
        )
        assert resp.status_code == 404
