"""Unit tests for gateway progress API."""

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway.app.api.auth import get_user_id_dependency
from gateway.app.api.progress import router
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


class TestDashboard:
    def test_dashboard_no_auth(self):
        """No auth → 401."""
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/progress/dashboard")
        assert resp.status_code == 401

    def test_dashboard_empty(self, client, mock_db, valid_token):
        mock_scalar = MagicMock()
        mock_scalar.scalar.return_value = 0
        mock_db.execute.return_value = mock_scalar

        resp = client.get(
            "/api/progress/dashboard",
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data
        assert "trend" in data


class TestMasteryList:
    def test_mastery_no_auth(self):
        """No auth → 401."""
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/progress/mastery")
        assert resp.status_code == 401

    def test_mastery_empty(self, client, mock_db, valid_token):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        resp = client.get(
            "/api/progress/mastery",
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        assert resp.status_code == 200
        assert resp.json() == []
