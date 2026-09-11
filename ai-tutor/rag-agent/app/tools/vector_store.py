"""向量存储 - pgvector"""

from uuid import UUID

from sqlalchemy import Float, cast, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import Chunk, Document


async def search_similar(
    db: AsyncSession,
    query_embedding: list[float],
    user_id: UUID,
    top_k: int = 20,
    similarity_threshold: float = 0.5,
) -> list[tuple[Chunk, float]]:
    """
    搜索相似的知识块

    Args:
        db: 数据库会话
        query_embedding: 查询嵌入向量
        user_id: 用户 ID
        top_k: 返回数量
        similarity_threshold: 相似度阈值

    Returns:
        (Chunk, similarity_score) 列表
    """
    # 使用 pgvector 的余弦相似度搜索
    query = text("""
        SELECT c.*,
               1 - (c.embedding <=> :embedding) as similarity
        FROM chunks c
        JOIN documents d ON c.document_id = d.id
        WHERE d.user_id = :user_id
          AND d.deleted_at IS NULL
          AND 1 - (c.embedding <=> :embedding) > :threshold
        ORDER BY c.embedding <=> :embedding
        LIMIT :limit
    """)

    result = await db.execute(
        query,
        {
            "embedding": str(query_embedding),
            "user_id": user_id,
            "threshold": similarity_threshold,
            "limit": top_k,
        },
    )

    rows = result.fetchall()

    chunks_with_scores = []
    for row in rows:
        chunk = Chunk(
            id=row.id,
            document_id=row.document_id,
            content=row.content,
            metadata_=row.metadata,
            chunk_index=row.chunk_index,
            token_count=row.token_count,
            created_at=row.created_at,
        )
        chunks_with_scores.append((chunk, row.similarity))

    return chunks_with_scores


async def search_by_keywords(
    db: AsyncSession,
    keywords: list[str],
    user_id: UUID,
    top_k: int = 20,
) -> list[tuple[Chunk, float]]:
    """
    关键词搜索（BM25 风格）

    Args:
        db: 数据库会话
        keywords: 关键词列表
        user_id: 用户 ID
        top_k: 返回数量

    Returns:
        (Chunk, relevance_score) 列表
    """
    relevance = (cast(func.count(), Float) / len(keywords)).label("relevance")
    query = (
        select(
            Chunk.id,
            Chunk.document_id,
            Chunk.content,
            Chunk.metadata_,
            Chunk.chunk_index,
            Chunk.token_count,
            Chunk.created_at,
            relevance,
        )
        .join(Document, Document.id == Chunk.document_id)
        .where(
            Document.user_id == user_id,
            Document.deleted_at.is_(None),
            or_(*[Chunk.content.ilike(f"%{kw}%") for kw in keywords]),
        )
        .group_by(Chunk.id)
        .order_by(relevance.desc())
        .limit(top_k)
    )

    result = await db.execute(query)

    rows = result.fetchall()

    chunks_with_scores = []
    for row in rows:
        chunk = Chunk(
            id=row.id,
            document_id=row.document_id,
            content=row.content,
            metadata_=row.metadata,
            chunk_index=row.chunk_index,
            token_count=row.token_count,
            created_at=row.created_at,
        )
        chunks_with_scores.append((chunk, row.relevance))

    return chunks_with_scores
