"""Tests for rag-agent search_service."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


@pytest.fixture
def db():
    return AsyncMock()


class TestSearchKnowledge:
    @pytest.mark.asyncio
    async def test_basic_search(self, db, rag_service_modules):
        with (
            patch(
                "app.services.search_service.rewrite_query",
                new_callable=AsyncMock,
            ) as mock_rewrite,
            patch(
                "app.services.search_service.hybrid_search",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch("app.services.search_service.rerank", new_callable=AsyncMock, return_value=[]),
        ):
            mock_rewrite.return_value = MagicMock(original="query", variants=["v1", "v2"])
            result = await rag_service_modules.search_knowledge(db, "query", uuid4())
            assert result.sources == []
            assert len(result.rewritten_queries) == 3

    @pytest.mark.asyncio
    async def test_no_rewrite(self, db, rag_service_modules):
        with (
            patch(
                "app.services.search_service.hybrid_search",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch("app.services.search_service.rerank", new_callable=AsyncMock, return_value=[]),
        ):
            result = await rag_service_modules.search_knowledge(
                db,
                "query",
                uuid4(),
                rewrite=False,
            )
            assert result.rewritten_queries == ["query"]

    @pytest.mark.asyncio
    async def test_with_results(self, db, rag_service_modules):
        mock_chunk = MagicMock()
        mock_chunk.id = uuid4()
        mock_chunk.document_id = uuid4()
        mock_chunk.content = "content"
        mock_chunk.metadata_ = {}
        mock_reranked = MagicMock()
        mock_reranked.chunk = mock_chunk
        mock_reranked.score = 0.9
        with (
            patch(
                "app.services.search_service.rewrite_query",
                new_callable=AsyncMock,
            ) as mock_rewrite,
            patch(
                "app.services.search_service.hybrid_search",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "app.services.search_service.rerank",
                new_callable=AsyncMock,
                return_value=[mock_reranked],
            ),
        ):
            mock_rewrite.return_value = MagicMock(original="query", variants=[])
            result = await rag_service_modules.search_knowledge(db, "query", uuid4())
            assert len(result.sources) == 1
            assert result.sources[0]["relevance_score"] == 0.9


class TestGetKnowledgeContext:
    @pytest.mark.asyncio
    async def test_empty_sources(self, db, rag_service_modules):
        with patch(
            "app.services.search_service.search_knowledge",
            new_callable=AsyncMock,
        ) as mock_search:
            mock_search.return_value = MagicMock(sources=[])
            result = await rag_service_modules.get_knowledge_context(db, "query", uuid4())
            assert "未找到" in result

    @pytest.mark.asyncio
    async def test_with_sources(self, db, rag_service_modules):
        mock_search_result = MagicMock()
        mock_search_result.sources = [
            {"content": "Python is great", "relevance_score": 0.9},
        ]
        with patch(
            "app.services.search_service.search_knowledge",
            new_callable=AsyncMock,
            return_value=mock_search_result,
        ):
            result = await rag_service_modules.get_knowledge_context(db, "query", uuid4())
            assert "Python is great" in result

    @pytest.mark.asyncio
    async def test_token_limit(self, db, rag_service_modules):
        long_content = "x" * 5000
        mock_search_result = MagicMock()
        mock_search_result.sources = [
            {"content": long_content, "relevance_score": 0.9},
        ]
        with patch(
            "app.services.search_service.search_knowledge",
            new_callable=AsyncMock,
            return_value=mock_search_result,
        ):
            result = await rag_service_modules.get_knowledge_context(
                db,
                "query",
                uuid4(),
                max_tokens=100,
            )
            assert len(result) < len(long_content)
