"""Unit tests for gateway main.py."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from gateway.app.main import app


@pytest.fixture
def client():
    with patch("gateway.app.main.init_db", new_callable=AsyncMock):
        yield TestClient(app, raise_server_exceptions=False)


class TestHealthCheck:
    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["service"] == "gateway"


class TestRoot:
    def test_root_returns_info(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "AI Tutor Gateway"
        assert data["version"] == "0.1.0"
        assert data["docs"] == "/docs"
