"""文档服务"""

import hashlib
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import Chunk, Document, ImportBatch

from ..tools import chunk_document, embed_chunks, fetch_document, parse_document


async def check_duplicate(
    db: AsyncSession,
    user_id: UUID,
    source_type: str,
    source_url: str | None = None,
    _file_path: str | None = None,
    content: str | None = None,
) -> Document | None:
    """
    检查文档是否重复

    Args:
        db: 数据库会话
        user_id: 用户 ID
        source_type: 来源类型
        source_url: 来源 URL
        _file_path: 文件路径
        content: 文件内容（用于计算 hash）

    Returns:
        重复的文档，如果没有重复返回 None
    """
    if source_type == "url" and source_url:
        result = await db.execute(
            select(Document).where(
                Document.user_id == user_id,
                Document.source_url == source_url,
                Document.deleted_at.is_(None),
            ),
        )
        return result.scalar_one_or_none()

    if source_type == "file" and content:
        file_hash = hashlib.sha256(content.encode()).hexdigest()
        result = await db.execute(
            select(Document).where(
                Document.user_id == user_id,
                Document.file_hash == file_hash,
                Document.deleted_at.is_(None),
            ),
        )
        return result.scalar_one_or_none()

    return None


async def process_document(
    db: AsyncSession,
    user_id: UUID,
    source_type: str,
    source_url: str | None = None,
    file_path: str | None = None,
    content: str | None = None,
    title: str | None = None,
    tags: list[str] = None,
    scrape_method: str = "auto",
) -> Document:
    """
    处理文档（抓取、解析、切分、向量化、存储）

    Args:
        db: 数据库会话
        user_id: 用户 ID
        source_type: 来源类型
        source_url: 来源 URL
        file_path: 文件路径
        content: 文件内容
        title: 文档标题
        tags: 标签
        scrape_method: 抓取方法

    Returns:
        处理后的文档
    """
    if tags is None:
        tags = []

    # 创建文档记录
    document = Document(
        user_id=user_id,
        title=title or "Untitled",
        source_type=source_type,
        source_url=source_url,
        file_path=file_path,
        content=content,
        tags=tags,
        status="processing",
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    try:
        # 如果是 URL，抓取内容
        if source_type == "url" and source_url:
            fetch_result = await fetch_document(source_url, method=scrape_method)

            if not fetch_result.success:
                document.status = "failed"
                document.error_message = fetch_result.error
                await db.commit()
                return document

            document.content = fetch_result.content
            if fetch_result.title:
                document.title = fetch_result.title
            document.raw_html = fetch_result.content
            document.scrape_method = fetch_result.method

        # 解析文档
        parsed = parse_document(document.content, document.title)
        document.title = parsed.title or document.title

        # 切分文档
        chunks = chunk_document(parsed.content)

        if not chunks:
            document.status = "failed"
            document.error_message = "No chunks generated"
            await db.commit()
            return document

        # 生成嵌入
        texts = [chunk.content for chunk in chunks]
        embed_result = await embed_chunks(texts)

        if not embed_result.success:
            document.status = "failed"
            document.error_message = f"Embedding failed: {embed_result.error}"
            await db.commit()
            return document

        # 存储知识块
        for _, (chunk, embedding) in enumerate(zip(chunks, embed_result.embeddings, strict=False)):
            db_chunk = Chunk(
                document_id=document.id,
                content=chunk.content,
                embedding=embedding,
                metadata_=chunk.metadata,
                chunk_index=chunk.index,
                token_count=chunk.metadata.get("token_estimate"),
            )
            db.add(db_chunk)

        # 更新文档状态
        document.chunk_count = len(chunks)
        document.status = "completed"
        document.processed_at = datetime.utcnow()

        # 计算文件 hash
        if content:
            document.file_hash = hashlib.sha256(content.encode()).hexdigest()

        await db.commit()
        await db.refresh(document)

        return document

    except Exception as e:
        document.status = "failed"
        document.error_message = str(e)
        await db.commit()
        return document


async def batch_import(
    db: AsyncSession,
    user_id: UUID,
    sources: list[dict],
    tags: list[str] = None,
    on_duplicate: str = "ask",
) -> dict:
    """
    批量导入文档

    Args:
        db: 数据库会话
        user_id: 用户 ID
        sources: 来源列表 [{"type": "url", "value": "..."}, ...]
        tags: 标签
        on_duplicate: 重复处理策略 (ask, skip, overwrite)

    Returns:
        导入结果
    """
    if tags is None:
        tags = []

    # 创建批量导入记录
    batch = ImportBatch(
        user_id=user_id,
        total_count=len(sources),
        status="processing",
    )
    db.add(batch)
    await db.commit()
    await db.refresh(batch)

    results = []
    duplicates = []

    for source in sources:
        source_type = source.get("type")
        source_value = source.get("value")

        # 检查重复
        existing = await check_duplicate(
            db,
            user_id,
            source_type,
            source_url=source_value if source_type == "url" else None,
            content=source_value if source_type == "file" else None,
        )

        if existing:
            if on_duplicate == "skip":
                batch.skipped_count += 1
                results.append(
                    {
                        "source": source,
                        "status": "skipped",
                        "reason": "duplicate",
                    },
                )
                continue
            if on_duplicate == "ask":
                duplicates.append(
                    {
                        "source_id": str(uuid4()),
                        "existing_doc_id": str(existing.id),
                        "existing_title": existing.title,
                        "source": source,
                    },
                )
                continue
            # overwrite 模式下继续处理
            existing.deleted_at = datetime.utcnow()
            from sqlalchemy import update

            await db.execute(
                update(Chunk)
                .where(Chunk.document_id == existing.id)
                .values(deleted_at=datetime.utcnow()),
            )
            await db.commit()

        # 处理文档
        document = await process_document(
            db,
            user_id,
            source_type,
            source_url=source_value if source_type == "url" else None,
            content=source_value if source_type == "file" else None,
            tags=tags,
        )

        if document.status == "completed":
            batch.completed_count += 1
            results.append(
                {
                    "source": source,
                    "status": "completed",
                    "document_id": str(document.id),
                    "title": document.title,
                    "chunk_count": document.chunk_count,
                },
            )
        else:
            batch.failed_count += 1
            results.append(
                {
                    "source": source,
                    "status": "failed",
                    "error": document.error_message,
                },
            )

    # 更新批量导入状态
    if batch.failed_count == 0:
        batch.status = "completed"
    elif batch.completed_count == 0:
        batch.status = "failed"
    else:
        batch.status = "partial"

    batch.completed_at = datetime.utcnow()
    await db.commit()

    documents = []
    for r in results:
        if r.get("status") == "completed" and r.get("document_id"):
            doc_result = await db.execute(
                select(Document).where(Document.id == UUID(r["document_id"])),
            )
            doc = doc_result.scalar_one_or_none()
            if doc:
                documents.append(doc)

    dup_list = []
    for d in duplicates:
        dup_list.append(
            {
                "source_id": d["source_id"],
                "existing_doc_id": d["existing_doc_id"],
                "existing_title": d["existing_title"],
                "source": d["source"],
                "message": f"文档 '{d['existing_title']}' 已存在",
            },
        )

    return {
        "batch_id": batch.id,
        "total": batch.total_count,
        "completed": batch.completed_count,
        "failed": batch.failed_count,
        "skipped": batch.skipped_count,
        "documents": documents,
        "duplicates": dup_list,
    }


async def retry_document(
    db: AsyncSession,
    user_id: UUID,
    document_id: UUID,
) -> Document | None:
    """
    重新处理失败的文档

    Args:
        db: 数据库会话
        user_id: 用户 ID
        document_id: 文档 ID

    Returns:
        重新处理后的文档
    """
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == user_id,
            Document.deleted_at.is_(None),
        ),
    )
    document = result.scalar_one_or_none()
    if not document:
        return None

    # 清理旧的 chunks，避免重复
    from sqlalchemy import update

    await db.execute(
        update(Chunk).where(Chunk.document_id == document.id).values(deleted_at=datetime.utcnow()),
    )

    # 重置旧文档，复用其来源重新处理
    document.status = "processing"
    document.error_message = None
    document.chunk_count = 0
    document.processed_at = None
    await db.commit()

    try:
        if document.source_type == "url" and document.source_url:
            fetch_result = await fetch_document(
                document.source_url,
                method=document.scrape_method or "auto",
            )
            if not fetch_result.success:
                document.status = "failed"
                document.error_message = fetch_result.error
                await db.commit()
                return document
            document.content = fetch_result.content
            if fetch_result.title:
                document.title = fetch_result.title
            document.raw_html = fetch_result.content
            document.scrape_method = fetch_result.method

        parsed = parse_document(document.content, document.title)
        document.title = parsed.title or document.title

        chunks = chunk_document(parsed.content)
        if not chunks:
            document.status = "failed"
            document.error_message = "No chunks generated"
            await db.commit()
            return document

        texts = [chunk.content for chunk in chunks]
        embed_result = await embed_chunks(texts)
        if not embed_result.success:
            document.status = "failed"
            document.error_message = f"Embedding failed: {embed_result.error}"
            await db.commit()
            return document

        for _, (chunk, embedding) in enumerate(zip(chunks, embed_result.embeddings, strict=False)):
            db_chunk = Chunk(
                document_id=document.id,
                content=chunk.content,
                embedding=embedding,
                metadata_=chunk.metadata,
                chunk_index=chunk.index,
                token_count=chunk.metadata.get("token_estimate"),
            )
            db.add(db_chunk)

        document.chunk_count = len(chunks)
        document.status = "completed"
        document.processed_at = datetime.utcnow()
        if document.content:
            document.file_hash = hashlib.sha256(document.content.encode()).hexdigest()

        await db.commit()
        await db.refresh(document)
        return document

    except Exception as e:
        document.status = "failed"
        document.error_message = str(e)
        await db.commit()
        return document
