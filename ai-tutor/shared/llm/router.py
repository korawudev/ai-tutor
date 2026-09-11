"""LLM 路由 - 动态选择 LLM 提供商"""

import time
from enum import Enum
from typing import Any

import httpx

from shared.utils.config import settings


class LLMProvider(str, Enum):
    """LLM 提供商"""

    SILICONFLOW = "siliconflow"
    DEEPSEEK = "deepseek"
    QWEN = "qwen"
    GLM = "glm"


class LLMRouter:
    """
    LLM 动态路由器

    当一个提供商额度用完或瞬时失败时，自动切换到下一个；失败冷却后重试，
    避免永久拉黑唯一可用 provider。
    """

    # 提供商优先级
    PROVIDER_PRIORITY = [
        LLMProvider.SILICONFLOW,
        LLMProvider.DEEPSEEK,
        LLMProvider.QWEN,
        LLMProvider.GLM,
    ]

    # 冷却时间（秒）：provider 失败后等待多久再重试
    FAIL_COOLDOWN_SECONDS = 30

    # 模型映射
    MODEL_MAP = {
        LLMProvider.SILICONFLOW: {
            "chat": "deepseek-ai/DeepSeek-V3",
            "embedding": "BAAI/bge-m3",
            "reranker": "BAAI/bge-reranker-v2-m3",
        },
        LLMProvider.DEEPSEEK: {
            "chat": "deepseek-chat",
        },
        LLMProvider.QWEN: {
            "chat": "qwen-turbo",
        },
        LLMProvider.GLM: {
            "chat": "glm-4-flash",
        },
    }

    KEY_FIELDS = {
        LLMProvider.SILICONFLOW: "SILICONFLOW_API_KEY",
        LLMProvider.DEEPSEEK: "DEEPSEEK_API_KEY",
        LLMProvider.QWEN: "QWEN_API_KEY",
        LLMProvider.GLM: "GLM_API_KEY",
    }

    def __init__(self):
        self._failed_at: dict[LLMProvider, float] = {}
        self._client = httpx.AsyncClient(timeout=60.0)

    def _has_key(self, provider: LLMProvider) -> bool:
        return bool(getattr(settings, self.KEY_FIELDS[provider], None))

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        provider: LLMProvider | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs,
    ) -> dict[str, Any]:
        """
        调用 LLM Chat API

        Args:
            messages: 消息列表
            model: 指定模型（可选）
            provider: 指定提供商（可选）
            temperature: 温度
            max_tokens: 最大 token 数

        Returns:
            {"content": "...", "model": "...", "provider": "...", "usage": {...}}
        """
        providers_to_try = [provider] if provider else self.PROVIDER_PRIORITY

        for prov in providers_to_try:
            if not self._has_key(prov):
                continue
            last_fail = self._failed_at.get(prov)
            if (
                last_fail is not None
                and (time.monotonic() - last_fail) < self.FAIL_COOLDOWN_SECONDS
            ):
                continue

            try:
                return await self._call_provider(
                    prov,
                    messages,
                    model,
                    temperature,
                    max_tokens,
                    **kwargs,
                )
            except Exception as e:
                print(f"LLM provider {prov} failed: {e}")
                self._failed_at[prov] = time.monotonic()
                continue

        # 所有提供商都失败
        raise Exception("All LLM providers failed")

    async def _call_provider(
        self,
        provider: LLMProvider,
        messages: list[dict[str, str]],
        model: str | None,
        temperature: float,
        max_tokens: int,
        **_kwargs,
    ) -> dict[str, Any]:
        """调用具体的提供商"""
        api_key = getattr(settings, self.KEY_FIELDS[provider], None)
        if provider == LLMProvider.SILICONFLOW:
            return await self._call_siliconflow(messages, model, temperature, max_tokens)
        if provider == LLMProvider.DEEPSEEK:
            return await self._call_openai_compatible(
                "https://api.deepseek.com/v1",
                messages,
                model or "deepseek-chat",
                api_key,
                temperature,
                max_tokens,
            )
        if provider == LLMProvider.QWEN:
            return await self._call_openai_compatible(
                "https://dashscope.aliyuncs.com/compatible-mode/v1",
                messages,
                model or "qwen-turbo",
                api_key,
                temperature,
                max_tokens,
            )
        if provider == LLMProvider.GLM:
            return await self._call_openai_compatible(
                "https://open.bigmodel.cn/api/paas/v4",
                messages,
                model or "glm-4-flash",
                api_key,
                temperature,
                max_tokens,
            )
        raise ValueError(f"Unknown provider: {provider}")

    async def _call_siliconflow(
        self,
        messages: list[dict[str, str]],
        model: str | None,
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        """调用硅基流动 API"""
        url = f"{settings.SILICONFLOW_BASE_URL}/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.SILICONFLOW_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model or settings.DEFAULT_LLM_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        response = await self._client.post(url, json=payload, headers=headers)
        response.raise_for_status()

        data = response.json()
        return {
            "content": data["choices"][0]["message"]["content"],
            "model": data["model"],
            "provider": "siliconflow",
            "usage": data.get("usage", {}),
        }

    async def _call_openai_compatible(
        self,
        base_url: str,
        messages: list[dict[str, str]],
        model: str,
        api_key: str,
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        """调用 OpenAI 兼容 API"""
        url = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        response = await self._client.post(url, json=payload, headers=headers)
        response.raise_for_status()

        data = response.json()
        return {
            "content": data["choices"][0]["message"]["content"],
            "model": data["model"],
            "provider": base_url.split("//")[1].split(".")[0],
            "usage": data.get("usage", {}),
        }

    async def embed(
        self,
        texts: list[str],
        _provider: LLMProvider | None = None,
    ) -> list[list[float]]:
        """
        生成文本嵌入

        Args:
            texts: 文本列表
            provider: 指定提供商（可选）

        Returns:
            嵌入向量列表
        """
        url = f"{settings.SILICONFLOW_BASE_URL}/embeddings"
        headers = {
            "Authorization": f"Bearer {settings.SILICONFLOW_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.DEFAULT_EMBEDDING_MODEL,
            "input": texts,
        }

        response = await self._client.post(url, json=payload, headers=headers)
        response.raise_for_status()

        data = response.json()
        return [item["embedding"] for item in data["data"]]

    async def close(self):
        """关闭 HTTP 客户端"""
        await self._client.aclose()


# 全局实例
llm_router = LLMRouter()
