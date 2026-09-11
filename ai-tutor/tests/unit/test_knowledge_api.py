"""Tests for knowledge-agent documents API."""

from datetime import datetime
from unittest.mock import MagicMock
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from shared.database import get_db
from shared.models import Document


def _setup_knowledge_agent():
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
    agent_app = str(root / "knowledge-agent" / "app")
    app_pkg = types.ModuleType("app")
    app_pkg.__path__ = [agent_app]
    sys.modules["app"] = app_pkg


class TestListDocuments:
    def test_no_auth(self):
        _setup_knowledge_agent()
        from app.api.documents import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/documents")
        assert resp.status_code == 401

    def test_empty(self, mock_db, user_id):
        _setup_knowledge_agent()
        from app.api.documents import get_user_id_dependency, router

        app = FastAPI()

        async def override_uid():
            return user_id

        async def override_db():
            yield mock_db

        app.dependency_overrides[get_user_id_dependency] = override_uid
        app.dependency_overrides[get_db] = override_db
        app.include_router(router)
        client = TestClient(app, raise_server_exceptions=False)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result
        resp = client.get("/api/documents", headers={"Authorization": "Bearer dummy"})
        assert resp.status_code == 200
        assert resp.json() == []


class TestGetDocument:
    def test_not_found(self, mock_db, user_id):
        _setup_knowledge_agent()
        from app.api.documents import get_user_id_dependency, router

        app = FastAPI()

        async def override_uid():
            return user_id

        async def override_db():
            yield mock_db

        app.dependency_overrides[get_user_id_dependency] = override_uid
        app.dependency_overrides[get_db] = override_db
        app.include_router(router)
        client = TestClient(app, raise_server_exceptions=False)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        resp = client.get(
            f"/api/documents/{uuid4()}",
            headers={"Authorization": "Bearer dummy"},
        )
        assert resp.status_code == 404


class TestDeleteDocument:
    def test_not_found(self, mock_db, user_id):
        _setup_knowledge_agent()
        from app.api.documents import get_user_id_dependency, router

        app = FastAPI()

        async def override_uid():
            return user_id

        async def override_db():
            yield mock_db

        app.dependency_overrides[get_user_id_dependency] = override_uid
        app.dependency_overrides[get_db] = override_db
        app.include_router(router)
        client = TestClient(app, raise_server_exceptions=False)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        resp = client.delete(
            f"/api/documents/delete/{uuid4()}",
            headers={"Authorization": "Bearer dummy"},
        )
        assert resp.status_code == 404

    def test_delete_success(self, mock_db, user_id):
        _setup_knowledge_agent()
        from app.api.documents import get_user_id_dependency, router

        app = FastAPI()

        async def override_uid():
            return user_id

        async def override_db():
            yield mock_db

        app.dependency_overrides[get_user_id_dependency] = override_uid
        app.dependency_overrides[get_db] = override_db
        app.include_router(router)
        client = TestClient(app, raise_server_exceptions=False)

        doc = Document(
            id=uuid4(),
            user_id=user_id,
            title="Test",
            source_type="url",
            status="completed",
            tags=[],
            chunk_count=5,
            created_at=datetime.utcnow(),
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = doc
        mock_db.execute.return_value = mock_result
        resp = client.delete(
            f"/api/documents/delete/{doc.id}",
            headers={"Authorization": "Bearer dummy"},
        )
        assert resp.status_code == 204
        mock_db.commit.assert_called()
