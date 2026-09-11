"""Reranker - 重排序"""

from dataclasses import dataclass

import httpx

from shared.models import Chunk
from shared.utils.config import settings


@dataclass
class RerankedResult:
    """重排序结果"""

    chunk: Chunk
    score: float
    original_score: float


async def rerank(
    query: str,
    chunks: list[tuple[Chunk, float]],
    top_k: int = 5,
) -> list[RerankedResult]:
    """
    使用 Reranker 重排序

    Args:
        query: 查询文本
        chunks: 候选块列表 [(chunk, score), ...]
        top_k: 返回数量

    Returns:
        重排序后的结果
    """
    if not chunks:
        return []

    try:
        # 使用 BGE-Reranker-v2-m3
        async with httpx.AsyncClient(timeout=60.0) as client:
            url = f"{settings.SILICONFLOW_BASE_URL}/rerank"
            headers = {
                "Authorization": f"Bearer {settings.SILICONFLOW_API_KEY}",
                "Content-Type": "application/json",
            }

            # 准备文档
            documents = [chunk.content for chunk, _ in chunks]

            payload = {
                "model": settings.DEFAULT_RERANKER_MODEL,
                "query": query,
                "documents": documents,
                "top_n": top_k,
                "return_documents": False,
            }

            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()

            data = response.json()
            results = data.get("results", [])

            # 构建结果
            reranked = []
            for result in results:
                index = result.get("index")
                score = result.get("relevance_score", 0)

                if index < len(chunks):
                    chunk, original_score = chunks[index]
                    reranked.append(
                        RerankedResult(
                            chunk=chunk,
                            score=score,
                            original_score=original_score,
                        ),
                    )

            return reranked[:top_k]

    except Exception as e:
        print(f"Reranking failed: {e}")

        # 失败时返回原始排序
        return [
            RerankedResult(
                chunk=chunk,
                score=score,
                original_score=score,
            )
            for chunk, score in chunks[:top_k]
        ]
