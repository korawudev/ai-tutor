"""Unit tests for gateway auth API."""

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway.app.api.auth import get_user_id_dependency, router
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


class TestAuthDependency:
    def test_missing_auth_header(self):
        """No auth header → 401 (dependency check before body validation)."""
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_invalid_auth_header(self):
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/auth/me", headers={"Authorization": "Invalid"})
        assert resp.status_code == 401

    def test_empty_bearer(self):
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/auth/me", headers={"Authorization": "Bearer "})
        assert resp.status_code == 401


class TestRegister:
    def test_register_duplicate_email(self, client, mock_db, sample_user):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db.execute.return_value = mock_result

        resp = client.post(
            "/api/auth/register",
            json={
                "email": "test@example.com",
                "username": "new",
                "password": "pass123",
            },
        )
        assert resp.status_code == 400


class TestLogin:
    def test_login_wrong_password(self, client, mock_db, sample_user):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db.execute.return_value = mock_result

        resp = client.post(
            "/api/auth/login",
            json={
                "email": "test@example.com",
                "password": "wrongpass",
            },
        )
        assert resp.status_code == 401
