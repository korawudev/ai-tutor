"""Tests for agent main.py health/root endpoints and shared/database."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


def _setup_agent(agent_name):
    import sys
    import types
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent.parent
    for k in list(sys.modules):
        if k == "app" or k.startswith("app."):
            del sys.modules[k]
    if "shared" not in sys.modules:
        shared_pkg = types.ModuleType("shared")
        shared_pkg.__path__ = [str(root / "shared")]
        sys.modules["shared"] = shared_pkg
    agent_app = str(root / agent_name / "app")
    app_pkg = types.ModuleType("app")
    app_pkg.__path__ = [agent_app]
    sys.modules["app"] = app_pkg


class TestKnowledgeAgentMain:
    def test_health(self):
        _setup_agent("knowledge-agent")
        with patch("shared.database.init_db", new_callable=AsyncMock):
            from app.main import app
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["service"] == "knowledge-agent"

    def test_root(self):
        _setup_agent("knowledge-agent")
        with patch("shared.database.init_db", new_callable=AsyncMock):
            from app.main import app
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.json()["docs"] == "/docs"


class TestRAGAgentMain:
    def test_health(self):
        _setup_agent("rag-agent")
        with patch("shared.database.init_db", new_callable=AsyncMock):
            from app.main import app
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["service"] == "rag-agent"

    def test_root(self):
        _setup_agent("rag-agent")
        with patch("shared.database.init_db", new_callable=AsyncMock):
            from app.main import app
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/")
        assert resp.status_code == 200
        assert "RAG" in resp.json()["service"]


class TestQuizAgentMain:
    def test_health(self):
        _setup_agent("quiz-agent")
        from app.main import app

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["service"] == "quiz-agent"

    def test_root(self):
        _setup_agent("quiz-agent")
        from app.main import app

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Quiz" in resp.json()["service"]


class TestProgressAgentMain:
    def test_health(self):
        _setup_agent("progress-agent")
        from app.main import app

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["service"] == "progress-agent"

    def test_root(self):
        _setup_agent("progress-agent")
        from app.main import app

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Progress" in resp.json()["service"]


class TestReviewAgentMain:
    def test_health(self):
        _setup_agent("review-agent")
        from app.main import app

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["service"] == "review-agent"

    def test_root(self):
        _setup_agent("review-agent")
        from app.main import app

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Review" in resp.json()["service"]


class TestSharedDatabase:
    @pytest.mark.asyncio
    async def test_get_db_yields_session(self):
        from shared.database import get_db

        gen = get_db()
        session = await gen.__anext__()
        assert session is not None
        with pytest.raises(StopAsyncIteration):
            await gen.__anext__()

    @pytest.mark.asyncio
    async def test_init_db(self):
        from shared.database import init_db

        mock_conn = AsyncMock()
        mock_conn.run_sync = AsyncMock()

        class FakeEngine:
            def begin(self):
                class Ctx:
                    async def __aenter__(self):
                        return mock_conn

                    async def __aexit__(self, *args):
                        return False

                return Ctx()

        with patch("shared.database.engine", FakeEngine()):
            await init_db()
            mock_conn.run_sync.assert_called_once()
