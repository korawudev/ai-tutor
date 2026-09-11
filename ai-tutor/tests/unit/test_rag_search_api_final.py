"""Tests for rag-agent search API and remaining coverage gaps."""
import sys
import os
import types
import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI


ROOT = os.path.join(os.path.dirname(__file__), "..", "..")


def _setup_rag_agent():
    for k in list(sys.modules):
        if k == "app" or k.startswith("app."):
            del sys.modules[k]
    shared_pkg = types.ModuleType("shared")
    shared_pkg.__path__ = [os.path.join(ROOT, "shared")]
    sys.modules["shared"] = shared_pkg
    agent_app = os.path.join(ROOT, "rag-agent", "app")
    app_pkg = types.ModuleType("app")
    app_pkg.__path__ = [agent_app]
    sys.modules["app"] = app_pkg


class TestRAGSearchAPI:
    def test_no_auth_query(self):
        _setup_rag_agent()
        from app.api.search import router
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/rag/query?query=test")
        assert resp.status_code == 401

    def test_no_auth_rewrite(self):
        _setup_rag_agent()
        from app.api.search import router
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/rag/rewrite?query=test")
        assert resp.status_code == 401

    def test_query_success(self):
        _setup_rag_agent()
        from app.api.search import router, get_user_id_dependency
        from shared.database import get_db

        mock_db = AsyncMock()
        mock_search = AsyncMock()

        app = FastAPI()

        async def override_uid():
            return uuid4()
        async def override_db():
            yield mock_db

        app.dependency_overrides[get_user_id_dependency] = override_uid
        app.dependency_overrides[get_db] = override_db
        app.include_router(router)
        client = TestClient(app, raise_server_exceptions=False)

        from shared.models import SearchResponse
        mock_response = SearchResponse(
            query="test", results=[], rewritten_query="test",
            total_results=0
        )
        mock_search.return_value = mock_response

        import app.api.search as search_mod
        original = search_mod.search_knowledge
        search_mod.search_knowledge = mock_search
        try:
            resp = client.post(
                "/api/rag/query?query=test",
                headers={"Authorization": "Bearer dummy"}
            )
            assert resp.status_code == 200
        finally:
            search_mod.search_knowledge = original

    def test_rewrite_success(self):
        _setup_rag_agent()
        from app.api.search import router, get_user_id_dependency

        mock_db = AsyncMock()

        app = FastAPI()
        app.dependency_overrides[get_user_id_dependency] = lambda: uuid4()
        app.dependency_overrides[lambda: None] = lambda: mock_db
        app.include_router(router)
        client = TestClient(app, raise_server_exceptions=False)

        mock_result = MagicMock()
        mock_result.original = "test query"
        mock_result.variants = ["variant 1", "variant 2"]
        with patch("app.tools.query_rewriter.rewrite_query", new_callable=AsyncMock, return_value=mock_result):
            resp = client.post(
                "/api/rag/rewrite?query=test+query",
                headers={"Authorization": "Bearer dummy"}
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["original"] == "test query"


class TestGatewayModelsImport:
    def test_imports(self):
        from gateway.app.models import Base, User, Thread, Run
        assert Base is not None
        assert User is not None
        assert Thread is not None
        assert Run is not None


class TestGatewaySchemasImport:
    def test_imports(self):
        from gateway.app.schemas import (
            UserCreate, UserResponse, UserLogin, Token,
            ThreadCreate, ThreadResponse,
            RunCreate, RunResponse, HITLResume, SSEEvent
        )
        assert UserCreate is not None
        assert UserResponse is not None
        assert ThreadCreate is not None
        assert RunCreate is not None
        assert HITLResume is not None
