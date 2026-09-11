"""Tests for knowledge-agent document_service."""
import pytest
from uuid import uuid4
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from shared.models import Document


@pytest.fixture
def db():
    return AsyncMock()


class TestCheckDuplicate:
    @pytest.mark.asyncio
    async def test_url_duplicate(self, db, knowledge_service_modules):
        doc = Document(
            id=uuid4(), user_id=uuid4(), title="Existing",
            source_type="url", source_url="https://example.com",
            status="completed", tags=[], chunk_count=5,
            created_at=datetime.utcnow()
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = doc
        db.execute.return_value = mock_result
        result = await knowledge_service_modules.check_duplicate(
            db, uuid4(), "url", source_url="https://example.com"
        )
        assert result is not None
        assert result.title == "Existing"

    @pytest.mark.asyncio
    async def test_url_no_duplicate(self, db, knowledge_service_modules):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute.return_value = mock_result
        result = await knowledge_service_modules.check_duplicate(
            db, uuid4(), "url", source_url="https://example.com"
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_file_duplicate(self, db, knowledge_service_modules):
        doc = Document(
            id=uuid4(), user_id=uuid4(), title="Existing",
            source_type="file", status="completed", tags=[],
            chunk_count=5, created_at=datetime.utcnow()
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = doc
        db.execute.return_value = mock_result
        result = await knowledge_service_modules.check_duplicate(
            db, uuid4(), "file", content="test content"
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_no_source(self, db, knowledge_service_modules):
        result = await knowledge_service_modules.check_duplicate(
            db, uuid4(), "unknown"
        )
        assert result is None


class TestProcessDocument:
    @pytest.mark.asyncio
    async def test_url_fetch_fails(self, db, knowledge_service_modules):
        db.refresh = AsyncMock()
        mock_fetch = MagicMock()
        mock_fetch.success = False
        mock_fetch.error = "Fetch failed"
        with patch("app.services.document_service.fetch_document", new_callable=AsyncMock, return_value=mock_fetch):
            result = await knowledge_service_modules.process_document(
                db, uuid4(), "url", source_url="https://example.com"
            )
            assert result.status == "failed"
            assert result.error_message == "Fetch failed"

    @pytest.mark.asyncio
    async def test_no_chunks_generated(self, db, knowledge_service_modules):
        db.refresh = AsyncMock()
        mock_fetch = MagicMock()
        mock_fetch.success = True
        mock_fetch.content = "content"
        mock_fetch.title = "Title"
        mock_fetch.method = "trafilatura"
        with patch("app.services.document_service.fetch_document", new_callable=AsyncMock, return_value=mock_fetch), \
             patch("app.services.document_service.parse_document") as mock_parse, \
             patch("app.services.document_service.chunk_document", return_value=[]):
            mock_parse.return_value = MagicMock(content="parsed", title="Title")
            result = await knowledge_service_modules.process_document(
                db, uuid4(), "url", source_url="https://example.com"
            )
            assert result.status == "failed"
            assert "No chunks" in result.error_message

    @pytest.mark.asyncio
    async def test_exception_handling(self, db, knowledge_service_modules):
        db.refresh = AsyncMock()
        with patch("app.services.document_service.fetch_document", new_callable=AsyncMock, side_effect=Exception("Network error")):
            result = await knowledge_service_modules.process_document(
                db, uuid4(), "url", source_url="https://example.com"
            )
            assert result.status == "failed"
            assert "Network error" in result.error_message


class TestBatchImport:
    @pytest.mark.asyncio
    async def test_empty_sources(self, db, knowledge_service_modules):
        db.refresh = AsyncMock()
        batch = MagicMock()
        batch.id = uuid4()
        batch.total_count = 0
        batch.completed_count = 0
        batch.failed_count = 0
        batch.skipped_count = 0
        with patch("app.services.document_service.ImportBatch", return_value=batch):
            result = await knowledge_service_modules.batch_import(db, uuid4(), [])
            assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_skip_duplicate(self, db, knowledge_service_modules):
        db.refresh = AsyncMock()
        batch = MagicMock()
        batch.id = uuid4()
        batch.total_count = 1
        batch.completed_count = 0
        batch.failed_count = 0
        batch.skipped_count = 0
        existing_doc = Document(
            id=uuid4(), user_id=uuid4(), title="Existing",
            source_type="url", source_url="https://example.com",
            status="completed", tags=[], chunk_count=5,
            created_at=datetime.utcnow()
        )
        with patch("app.services.document_service.ImportBatch", return_value=batch), \
             patch("app.services.document_service.check_duplicate", new_callable=AsyncMock, return_value=existing_doc):
            result = await knowledge_service_modules.batch_import(
                db, uuid4(),
                [{"type": "url", "value": "https://example.com"}],
                on_duplicate="skip"
            )
            assert result["skipped"] == 1
