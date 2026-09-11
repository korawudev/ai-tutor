"""SiliconFlow LLM 公共客户端 - JSON 结构化输出"""
import json
import os
import re
from typing import Any, Dict

import httpx

SILICONFLOW_BASE_URL = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
DEFAULT_MODEL = os.getenv("SILICONFLOW_MODEL", "deepseek-ai/DeepSeek-V3")


def chat_json(
    system_prompt: str,
    user_content: str,
    max_tokens: int = 1024,
    temperature: float = 0.3,
) -> Dict[str, Any]:
    """
    调用 SiliconFlow chat/completions 并抽取 JSON 对象。
    返回 dict；缺失字段由调用方 setdefault 兜底。
    """
    api_key = os.getenv("SILICONFLOW_API_KEY")
    if not api_key:
        raise RuntimeError("SILICONFLOW_API_KEY 未配置")

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    with httpx.Client(timeout=60.0) as client:
        resp = client.post(
            f"{SILICONFLOW_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": DEFAULT_MODEL, "messages": messages, "max_tokens": max_tokens, "temperature": temperature},
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]

    json_match = re.search(r"\{[\s\S]*\}", content)
    if not json_match:
        return {}
    return json.loads(json_match.group())