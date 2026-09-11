"""Unit tests for gateway documents proxy API."""
import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from fastapi import FastAPI

from gateway.app.api.documents import router
from gateway.app.api.auth import get_user_id_dependency


@pytest.fixture
def app(mock_db, user_id):
    app = FastAPI()

    async def override_get_user_id():
        return user_id

    app.dependency_overrides[get_user_id_dependency] = override_get_user_id
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)


def _make_httpx_response(status_code=200, json_data=None):
    """Create a MagicMock that behaves like an httpx.Response."""
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


class TestDocumentsProxy:
    def test_import_no_auth(self):
        """No auth header → 401."""
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/documents/import", json={
            "sources": [{"type": "url", "value": "https://example.com"}]
        })
        assert resp.status_code == 401

    def test_list_no_auth(self):
        """No auth header → 401."""
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/documents")
        assert resp.status_code == 401

    @patch("gateway.app.api.documents.httpx.AsyncClient")
    def test_import_proxies_to_knowledge_agent(self, mock_client_cls, client, valid_token):
        expected = {
            "batch_id": str(uuid4()), "total": 1, "completed": 1,
            "failed": 0, "skipped": 0, "documents": [], "duplicates": []
        }
        mock_resp = _make_httpx_response(200, expected)
        mock_client_cls.return_value = _make_httpx_client(mock_resp)

        resp = client.post(
            "/api/documents/import",
            json={"sources": [{"type": "url", "value": "https://example.com"}]},
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    @patch("gateway.app.api.documents.httpx.AsyncClient")
    def test_list_proxies_to_knowledge_agent(self, mock_client_cls, client, valid_token):
        mock_resp = _make_httpx_response(200, [])
        mock_client_cls.return_value = _make_httpx_client(mock_resp)

        resp = client.get(
            "/api/documents",
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert resp.status_code == 200
        assert resp.json() == []

    @patch("gateway.app.api.documents.httpx.AsyncClient")
    def test_proxy_error_handling(self, mock_client_cls, client, valid_token):
        mock_resp = _make_httpx_response(500, {"detail": "Knowledge agent error"})
        mock_client_cls.return_value = _make_httpx_client(mock_resp)

        resp = client.post(
            "/api/documents/import",
            json={"sources": [{"type": "url", "value": "https://x.com"}]},
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert resp.status_code == 500
