"""Tests for rag-agent hybrid_search, vector_store, and reranker."""
import pytest
from uuid import uuid4
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch


class TestExtractKeywords:
    def test_basic(self, rag_search_modules):
        result = rag_search_modules.extract_keywords("Python classes inheritance")
        assert "python" in result
        assert "classes" in result
        assert "inheritance" in result

    def test_filters_stop_words(self, rag_search_modules):
        result = rag_search_modules.extract_keywords("the is a test of the system")
        assert "test" in result
        assert "system" in result
        assert "the" not in result
        assert "is" not in result

    def test_filters_single_char_words(self, rag_search_modules):
        result = rag_search_modules.extract_keywords("a I x")
        assert len(result) == 0

    def test_empty(self, rag_search_modules):
        result = rag_search_modules.extract_keywords("")
        assert result == []


class TestHybridSearch:
    @pytest.mark.asyncio
    async def test_empty_results(self, rag_search_modules):
        db = AsyncMock()
        with patch("app.tools.hybrid_search.search_similar", new_callable=AsyncMock, return_value=[]), \
             patch("app.tools.hybrid_search.search_by_keywords", new_callable=AsyncMock, return_value=[]):
            result = await rag_search_modules.hybrid_search(db, "test query", [0.1]*10, uuid4())
            assert result == []

    @pytest.mark.asyncio
    async def test_vector_only(self, rag_search_modules):
        db = AsyncMock()
        mock_chunk = MagicMock()
        mock_chunk.id = uuid4()
        with patch("app.tools.hybrid_search.search_similar", new_callable=AsyncMock, return_value=[(mock_chunk, 0.9)]), \
             patch("app.tools.hybrid_search.search_by_keywords", new_callable=AsyncMock, return_value=[]):
            result = await rag_search_modules.hybrid_search(db, "test", [0.1]*10, uuid4())
            assert len(result) == 1
            assert result[0].source == "vector"

    @pytest.mark.asyncio
    async def test_keyword_only(self, rag_search_modules):
        db = AsyncMock()
        mock_chunk = MagicMock()
        mock_chunk.id = uuid4()
        with patch("app.tools.hybrid_search.search_similar", new_callable=AsyncMock, return_value=[]), \
             patch("app.tools.hybrid_search.search_by_keywords", new_callable=AsyncMock, return_value=[(mock_chunk, 0.8)]):
            result = await rag_search_modules.hybrid_search(db, "test", [0.1]*10, uuid4())
            assert len(result) == 1
            assert result[0].source == "keyword"

    @pytest.mark.asyncio
    async def test_both_sources(self, rag_search_modules):
        db = AsyncMock()
        mock_chunk = MagicMock()
        mock_chunk.id = uuid4()
        with patch("app.tools.hybrid_search.search_similar", new_callable=AsyncMock, return_value=[(mock_chunk, 0.9)]), \
             patch("app.tools.hybrid_search.search_by_keywords", new_callable=AsyncMock, return_value=[(mock_chunk, 0.8)]):
            result = await rag_search_modules.hybrid_search(db, "test", [0.1]*10, uuid4())
            assert len(result) == 1
            assert result[0].source == "both"

    @pytest.mark.asyncio
    async def test_top_k_limit(self, rag_search_modules):
        db = AsyncMock()
        chunks = []
        for _ in range(5):
            mc = MagicMock()
            mc.id = uuid4()
            chunks.append((mc, 0.9))
        with patch("app.tools.hybrid_search.search_similar", new_callable=AsyncMock, return_value=chunks), \
             patch("app.tools.hybrid_search.search_by_keywords", new_callable=AsyncMock, return_value=[]):
            result = await rag_search_modules.hybrid_search(db, "test", [0.1]*10, uuid4(), top_k=2)
            assert len(result) == 2


class TestSearchSimilar:
    @pytest.mark.asyncio
    async def test_empty(self, rag_search_modules):
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        db.execute.return_value = mock_result
        result = await rag_search_modules.search_similar(db, [0.1]*10, uuid4())
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
        result = await rag_search_modules.search_similar(db, [0.1]*10, uuid4())
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


class TestReranker:
    @pytest.mark.asyncio
    async def test_empty_chunks(self, rag_search_modules):
        result = await rag_search_modules.rerank("query", [], top_k=5)
        assert result == []

    @pytest.mark.asyncio
    async def test_fallback_on_error(self, rag_search_modules):
        mock_chunk = MagicMock()
        mock_chunk.id = uuid4()
        mock_chunk.content = "test"
        with patch("app.tools.reranker.httpx") as mock_httpx:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(side_effect=Exception("API error"))
            mock_httpx.AsyncClient.return_value = mock_client
            result = await rag_search_modules.rerank("query", [(mock_chunk, 0.8)], top_k=5)
            assert len(result) == 1
            assert result[0].score == 0.8

    @pytest.mark.asyncio
    async def test_successful_rerank(self, rag_search_modules):
        mock_chunk = MagicMock()
        mock_chunk.id = uuid4()
        mock_chunk.content = "test"
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [{"index": 0, "relevance_score": 0.95}]
        }
        mock_response.raise_for_status = MagicMock()
        with patch("app.tools.reranker.httpx") as mock_httpx:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_httpx.AsyncClient.return_value = mock_client
            result = await rag_search_modules.rerank("query", [(mock_chunk, 0.8)], top_k=5)
            assert len(result) == 1
            assert result[0].score == 0.95
            assert result[0].original_score == 0.8
