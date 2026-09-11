"""Tests for rag-agent vector_store."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


class TestSearchSimilar:
    @pytest.mark.asyncio
    async def test_empty(self, rag_search_modules):
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        db.execute.return_value = mock_result
        result = await rag_search_modules.search_similar(db, [0.1] * 10, uuid4())
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_chunks(self, rag_search_modules):
        db = AsyncMock()
        row = MagicMock()
        row.id = uuid4()
        row.document_id = uuid4()
        row.content = "test content"
        row.metadata = {}
        row.chunk_index = 0
        row.token_count = 10
        row.created_at = datetime.utcnow()
        row.similarity = 0.85
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [row]
        db.execute.return_value = mock_result
        result = await rag_search_modules.search_similar(db, [0.1] * 10, uuid4())
        assert len(result) == 1
        assert result[0][1] == 0.85


class TestSearchByKeywords:
    @pytest.mark.asyncio
    async def test_empty(self, rag_search_modules):
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        db.execute.return_value = mock_result
        result = await rag_search_modules.search_by_keywords(db, ["python"], uuid4())
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_chunks(self, rag_search_modules):
        db = AsyncMock()
        row = MagicMock()
        row.id = uuid4()
        row.document_id = uuid4()
        row.content = "python content"
        row.metadata = {}
        row.chunk_index = 0
        row.token_count = 10
        row.created_at = datetime.utcnow()
        row.relevance = 0.75
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [row]
        db.execute.return_value = mock_result
        result = await rag_search_modules.search_by_keywords(db, ["python"], uuid4())
        assert len(result) == 1
        assert result[0][1] == 0.75
