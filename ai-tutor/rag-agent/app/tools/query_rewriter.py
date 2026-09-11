"""查询改写"""

from dataclasses import dataclass

from shared.llm import llm_router


@dataclass
class RewrittenQuery:
    """改写后的查询"""

    original: str
    variants: list[str]


async def rewrite_query(
    query: str,
    num_variants: int = 4,
) -> RewrittenQuery:
    """
    查询改写 - 生成多个查询变体

    Args:
        query: 原始查询
        num_variants: 变体数量

    Returns:
        RewrittenQuery
    """
    prompt = f"""你是一个搜索查询优化专家。请将以下查询改写为 {num_variants} 个不同的搜索变体，\
用于检索相关知识。

原始查询: {query}

要求:
1. 保持语义一致
2. 使用不同的表达方式
3. 包含相关术语
4. 适合知识库检索

请返回 JSON 格式:
{{"variants": ["变体1", "变体2", "变体3", "变体4"]}}"""

    try:
        response = await llm_router.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=500,
        )

        content = response["content"]

        # 解析 JSON
        import json
        import re

        # 提取 JSON 部分
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            variants = data.get("variants", [])

            return RewrittenQuery(
                original=query,
                variants=variants[:num_variants],
            )

    except Exception as e:
        print(f"Query rewrite failed: {e}")

    # 失败时返回原始查询
    return RewrittenQuery(
        original=query,
        variants=[query],
    )
