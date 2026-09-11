"""Gateway API - Thread 管理"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db
from shared.models import Thread, ThreadCreate, ThreadResponse

from .auth import get_user_id_dependency

router = APIRouter(prefix="/api/threads", tags=["threads"])


@router.post("", response_model=ThreadResponse, status_code=status.HTTP_201_CREATED)
async def create_thread(
    thread_data: ThreadCreate,
    user_id: UUID = Depends(get_user_id_dependency),
    db: AsyncSession = Depends(get_db),
):
    """
    创建 Thread

    - agent_type: Agent 类型 (feynman, quiz, review, knowledge, progress)
    """
    thread = Thread(
        user_id=user_id,
        agent_type=thread_data.agent_type,
        state={},
        metadata_={},
    )
    db.add(thread)
    await db.commit()
    await db.refresh(thread)

    return ThreadResponse.model_validate(thread)


@router.get("", response_model=list[ThreadResponse])
async def list_threads(
    status: str | None = None,
    agent_type: str | None = None,
    limit: int = 20,
    offset: int = 0,
    user_id: UUID = Depends(get_user_id_dependency),
    db: AsyncSession = Depends(get_db),
):
    """
    列出用户的 Threads

    - status: 过滤状态 (active, completed, paused)
    - agent_type: 过滤 Agent 类型
    - limit: 返回数量限制
    - offset: 偏移量
    """
    query = select(Thread).where(Thread.user_id == user_id)

    if status:
        query = query.where(Thread.status == status)
    if agent_type:
        query = query.where(Thread.agent_type == agent_type)

    query = query.order_by(Thread.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    threads = result.scalars().all()

    return [ThreadResponse.model_validate(t) for t in threads]


@router.get("/{thread_id}", response_model=ThreadResponse)
async def get_thread(
    thread_id: UUID,
    user_id: UUID = Depends(get_user_id_dependency),
    db: AsyncSession = Depends(get_db),
):
    """获取 Thread 详情"""
    result = await db.execute(
        select(Thread).where(Thread.id == thread_id, Thread.user_id == user_id),
    )
    thread = result.scalar_one_or_none()

    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thread not found",
        )

    return ThreadResponse.model_validate(thread)


@router.delete("/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_thread(
    thread_id: UUID,
    user_id: UUID = Depends(get_user_id_dependency),
    db: AsyncSession = Depends(get_db),
):
    """删除 Thread"""
    result = await db.execute(
        select(Thread).where(Thread.id == thread_id, Thread.user_id == user_id),
    )
    thread = result.scalar_one_or_none()

    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thread not found",
        )

    await db.delete(thread)
    await db.commit()
