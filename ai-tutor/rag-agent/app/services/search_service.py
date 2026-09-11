from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ..tools import hybrid_search, rerank, rewrite_query


@dataclass
class SearchServiceResponse:
    sources: list[dict] = field(default_factory=list)
    rewritten_queries: list[str] = field(default_factory=list)
    search_latency_ms: int = 0


async def search_knowledge(
    db: AsyncSession,
    query: str,
    user_id: UUID,
    top_k: int = 5,
    rewrite: bool = True,
) -> SearchServiceResponse:
    import time

    start_time = time.time()

    rewritten_queries = [query]
    if rewrite:
        rewritten = await rewrite_query(query, num_variants=3)
        rewritten_queries = [rewritten.original] + rewritten.variants

    all_results = []
    for q in rewritten_queries:
        results = await hybrid_search(db, q, user_id, top_k=top_k * 2)
        all_results.extend(results)

    seen_ids = set()
    unique_results = []
    for result in all_results:
        chunk_id = (
            str(result.chunk.id) if hasattr(result, "chunk") else str(result.get("chunk_id", ""))
        )
        if chunk_id not in seen_ids:
            seen_ids.add(chunk_id)
            unique_results.append(result)

    chunk_score_pairs = []
    for r in unique_results:
        if hasattr(r, "chunk"):
            chunk_score_pairs.append((r.chunk, r.score))
        else:
            chunk_score_pairs.append((r, r.get("score", 0)))

    reranked = await rerank(query, chunk_score_pairs, top_k=top_k)

    sources = []
    for result in reranked:
        chunk = result.chunk if hasattr(result, "chunk") else result
        score = result.score if hasattr(result, "score") else 0
        sources.append(
            {
                "chunk_id": str(chunk.id),
                "document_id": str(chunk.document_id),
                "content": chunk.content,
                "relevance_score": score,
                "metadata": getattr(chunk, "metadata_", {}) or {},
            },
        )

    latency_ms = int((time.time() - start_time) * 1000)

    return SearchServiceResponse(
        sources=sources,
        rewritten_queries=rewritten_queries,
        search_latency_ms=latency_ms,
    )


async def get_knowledge_context(
    db: AsyncSession,
    query: str,
    user_id: UUID,
    max_tokens: int = 2000,
) -> str:
    response = await search_knowledge(db, query, user_id, top_k=5, rewrite=False)
    if not response.sources:
        return "未找到相关知识。"

    context_parts = []
    current_tokens = 0
    for source in response.sources:
        content = source["content"]
        estimated_tokens = len(content) // 2
        if current_tokens + estimated_tokens > max_tokens:
            break
        context_parts.append(f"【来源 {len(context_parts) + 1}】\n{content}")
        current_tokens += estimated_tokens

    return "\n\n".join(context_parts)
