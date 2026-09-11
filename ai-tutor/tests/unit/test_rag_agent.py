"""Unit tests for RAG-agent tools."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestQueryRewriter:
    @pytest.mark.asyncio
    async def test_rewrite_success(self, rag_modules):
        with patch("app.tools.query_rewriter.llm_router") as mock_router:
            mock_router.chat = AsyncMock(
                return_value={
                    "content": '{"variants": ["var1", "var2", "var3"]}',
                },
            )
            result = await rag_modules.rewrite_query("test query", num_variants=3)
            assert result.original == "test query"
            assert len(result.variants) == 3

    @pytest.mark.asyncio
    async def test_rewrite_llm_failure(self, rag_modules):
        with patch("app.tools.query_rewriter.llm_router") as mock_router:
            mock_router.chat = AsyncMock(side_effect=Exception("LLM error"))
            result = await rag_modules.rewrite_query("test query")
            assert result.original == "test query"
            assert result.variants == ["test query"]

    @pytest.mark.asyncio
    async def test_rewrite_no_json(self, rag_modules):
        with patch("app.tools.query_rewriter.llm_router") as mock_router:
            mock_router.chat = AsyncMock(return_value={"content": "no json here"})
            result = await rag_modules.rewrite_query("q")
            assert result.variants == ["q"]

    @pytest.mark.asyncio
    async def test_rewrite_truncates_variants(self, rag_modules):
        with patch("app.tools.query_rewriter.llm_router") as mock_router:
            mock_router.chat = AsyncMock(
                return_value={
                    "content": '{"variants": ["a","b","c","d","e","f"]}',
                },
            )
            result = await rag_modules.rewrite_query("q", num_variants=2)
            assert len(result.variants) == 2


class TestReranker:
    @pytest.mark.asyncio
    async def test_rerank_empty(self, rag_modules):
        result = await rag_modules.rerank("query", [], top_k=5)
        assert result == []

    @pytest.mark.asyncio
    async def test_rerank_api_failure_fallback(self, rag_modules):
        chunk = MagicMock()
        chunk.content = "content"
        with patch("app.tools.reranker.httpx.AsyncClient") as mock_client_cls:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(side_effect=Exception("API error"))
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_instance

            result = await rag_modules.rerank("query", [(chunk, 0.7)], top_k=1)
            assert len(result) == 1
            assert result[0].score == 0.7
