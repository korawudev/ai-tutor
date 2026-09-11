"""Unit tests for knowledge-agent tools."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestParseDocument:
    def test_parse_with_title(self, knowledge_modules):
        result = knowledge_modules.parse_document("Hello world content", title="My Title")
        assert result.title == "My Title"
        assert result.content == "Hello world content"
        assert result.metadata["char_count"] == 19

    def test_parse_extracts_md_heading(self, knowledge_modules):
        result = knowledge_modules.parse_document("# Heading\nSome content")
        assert result.title == "Heading"

    def test_parse_extracts_first_line_as_title(self, knowledge_modules):
        result = knowledge_modules.parse_document("Short Title\nMore content here")
        assert result.title == "Short Title"

    def test_parse_strips_content(self, knowledge_modules):
        result = knowledge_modules.parse_document("  padded  ")
        assert result.content == "padded"

    def test_parse_empty_content(self, knowledge_modules):
        result = knowledge_modules.parse_document("")
        assert result.content == ""
        assert result.metadata["char_count"] == 0

    def test_parse_long_first_line_not_title(self, knowledge_modules):
        long_line = "x" * 150
        result = knowledge_modules.parse_document(f"{long_line}\nrest")
        assert result.title != long_line


class TestChunkDocument:
    def test_chunk_empty(self, knowledge_modules):
        assert knowledge_modules.chunk_document("") == []

    def test_chunk_short_text(self, knowledge_modules):
        chunks = knowledge_modules.chunk_document("Short text")
        assert len(chunks) >= 1
        assert chunks[0].content == "Short text"
        assert chunks[0].index == 0

    def test_chunk_long_text(self, knowledge_modules):
        text = "Sentence. " * 200
        chunks = knowledge_modules.chunk_document(text, chunk_size=200)
        assert len(chunks) > 1

    def test_chunk_metadata(self, knowledge_modules):
        chunks = knowledge_modules.chunk_document("Some content here")
        assert "char_count" in chunks[0].metadata
        assert "token_estimate" in chunks[0].metadata

    def test_chunk_skips_empty(self, knowledge_modules):
        chunks = knowledge_modules.chunk_document("   ")
        assert len(chunks) == 0

    def test_chunk_custom_separators(self, knowledge_modules):
        text = "Part1===Part2===Part3===" * 20
        chunks = knowledge_modules.chunk_document(
            text,
            chunk_size=50,
            chunk_overlap=10,
            separators=["==="],
        )
        assert len(chunks) >= 2


class TestEmbedChunks:
    @pytest.mark.asyncio
    async def test_embed_success(self, knowledge_modules):
        with patch("app.tools.embed_document.llm_router") as mock_router:
            mock_router.embed = AsyncMock(return_value=[[0.1, 0.2, 0.3]])
            result = await knowledge_modules.embed_chunks(["hello"])
            assert result.success is True
            assert len(result.embeddings) == 1

    @pytest.mark.asyncio
    async def test_embed_failure(self, knowledge_modules):
        with patch("app.tools.embed_document.llm_router") as mock_router:
            mock_router.embed = AsyncMock(side_effect=Exception("API error"))
            result = await knowledge_modules.embed_chunks(["hello"])
            assert result.success is False
            assert "API error" in result.error

    @pytest.mark.asyncio
    async def test_embed_empty(self, knowledge_modules):
        result = await knowledge_modules.embed_chunks([])
        assert result.success is True
        assert result.embeddings == []

    @pytest.mark.asyncio
    async def test_embed_single(self, knowledge_modules):
        with patch("app.tools.embed_document.llm_router") as mock_router:
            mock_router.embed = AsyncMock(return_value=[[0.5, 0.6]])
            result = await knowledge_modules.embed_single("test")
            assert result == [0.5, 0.6]

    @pytest.mark.asyncio
    async def test_embed_single_failure(self, knowledge_modules):
        with patch("app.tools.embed_document.llm_router") as mock_router:
            mock_router.embed = AsyncMock(side_effect=Exception("fail"))
            result = await knowledge_modules.embed_single("test")
            assert result is None


class TestFetchDocument:
    @pytest.mark.asyncio
    async def test_fetch_trafilatura_success(self, knowledge_modules):
        with patch("app.tools.fetch_document.scrape_with_trafilatura") as mock_traf:
            mock_traf.return_value = MagicMock(success=True, content="content", title="title")
            result = await knowledge_modules.fetch_document(
                "https://example.com",
                method="trafilatura",
            )
            assert result.success is True
            assert result.method == "trafilatura"

    @pytest.mark.asyncio
    async def test_fetch_auto_fallback(self, knowledge_modules):
        with (
            patch("app.tools.fetch_document.scrape_with_trafilatura") as mock_traf,
            patch("app.tools.fetch_document.scrape_with_jina") as mock_jina,
        ):
            mock_traf.return_value = MagicMock(success=False, error="traf error")
            mock_jina.return_value = MagicMock(
                success=True,
                content="jina content",
                title="jina title",
            )
            result = await knowledge_modules.fetch_document("https://example.com", method="auto")
            assert result.success is True
            assert result.method == "jina"

    @pytest.mark.asyncio
    async def test_fetch_auto_all_fail(self, knowledge_modules):
        with (
            patch("app.tools.fetch_document.scrape_with_trafilatura") as mock_traf,
            patch("app.tools.fetch_document.scrape_with_jina") as mock_jina,
        ):
            mock_traf.return_value = MagicMock(success=False, error="traf err")
            mock_jina.return_value = MagicMock(success=False, error="jina err")
            result = await knowledge_modules.fetch_document("https://example.com", method="auto")
            assert result.success is False
            assert result.needs_fallback is True

    @pytest.mark.asyncio
    async def test_fetch_jina_method(self, knowledge_modules):
        with patch("app.tools.fetch_document.scrape_with_jina") as mock_jina:
            mock_jina.return_value = MagicMock(success=True, content="c", title="t", error=None)
            result = await knowledge_modules.fetch_document("https://example.com", method="jina")
            assert result.success is True
            assert result.method == "jina"

    @pytest.mark.asyncio
    async def test_fetch_unknown_method(self, knowledge_modules):
        result = await knowledge_modules.fetch_document("https://example.com", method="unknown")
        assert result.success is False
