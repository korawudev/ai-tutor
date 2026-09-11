"""Unit tests for shared LLM router."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.llm.router import LLMProvider, LLMRouter
from shared.utils.config import settings


@pytest.fixture
def router(monkeypatch):
    # llm_router 只尝试已配置 API key 的 provider，
    # 测试注入备用 key 以覆盖 fallback/指定 provider 场景
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "test-deepseek-key")
    monkeypatch.setattr(settings, "QWEN_API_KEY", "test-qwen-key")
    monkeypatch.setattr(settings, "GLM_API_KEY", "test-glm-key")
    return LLMRouter()


class TestLLMRouterInit:
    def test_init_sets_empty_failed(self, router):
        assert router._failed_at == {}

    def test_provider_priority(self):
        assert LLMProvider.SILICONFLOW in LLMRouter.PROVIDER_PRIORITY
        assert len(LLMRouter.PROVIDER_PRIORITY) == 4


class TestChat:
    @pytest.mark.asyncio
    async def test_chat_siliconflow_success(self, router):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello!"}}],
            "model": "deepseek-ai/DeepSeek-V3",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        mock_response.raise_for_status = MagicMock()

        router._client = AsyncMock()
        router._client.post = AsyncMock(return_value=mock_response)

        result = await router.chat([{"role": "user", "content": "Hi"}])
        assert result["content"] == "Hello!"
        assert result["provider"] == "siliconflow"

    @pytest.mark.asyncio
    async def test_chat_provider_fallback(self, router):
        fail_response = MagicMock()
        fail_response.raise_for_status.side_effect = Exception("Quota exceeded")

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = {
            "choices": [{"message": {"content": "OK"}}],
            "model": "deepseek-chat",
            "usage": {},
        }
        success_response.raise_for_status = MagicMock()

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return fail_response
            return success_response

        router._client = AsyncMock()
        router._client.post = mock_post

        result = await router.chat([{"role": "user", "content": "Hi"}])
        assert result["content"] == "OK"

    @pytest.mark.asyncio
    async def test_chat_all_providers_fail(self, router):
        router._client = AsyncMock()
        router._client.post = AsyncMock(side_effect=Exception("All down"))

        with pytest.raises(Exception, match="All LLM providers failed"):
            await router.chat([{"role": "user", "content": "Hi"}])

    @pytest.mark.asyncio
    async def test_chat_specified_provider(self, router):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "DeepSeek says hi"}}],
            "model": "deepseek-chat",
            "usage": {},
        }
        mock_response.raise_for_status = MagicMock()

        router._client = AsyncMock()
        router._client.post = AsyncMock(return_value=mock_response)

        result = await router.chat(
            [{"role": "user", "content": "Hi"}],
            provider=LLMProvider.DEEPSEEK,
        )
        assert result["content"] == "DeepSeek says hi"


class TestEmbed:
    @pytest.mark.asyncio
    async def test_embed_success(self, router):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [{"embedding": [0.1, 0.2, 0.3]}],
        }
        mock_response.raise_for_status = MagicMock()

        router._client = AsyncMock()
        router._client.post = AsyncMock(return_value=mock_response)

        result = await router.embed(["hello world"])
        assert result == [[0.1, 0.2, 0.3]]

    @pytest.mark.asyncio
    async def test_embed_failure(self, router):
        router._client = AsyncMock()
        router._client.post = AsyncMock(side_effect=Exception("API error"))

        with pytest.raises(Exception, match="API error"):
            await router.embed(["hello"])


class TestClose:
    @pytest.mark.asyncio
    async def test_close(self, router):
        router._client = AsyncMock()
        router._client.aclose = AsyncMock()
        await router.close()
        router._client.aclose.assert_called_once()
