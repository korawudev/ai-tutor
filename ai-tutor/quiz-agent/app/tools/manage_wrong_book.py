"""错题本管理"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import WrongQuestion


async def add_wrong_question(
    db: AsyncSession,
    user_id: UUID,
    quiz_id: UUID,
    question: dict,
    user_answer: str,
    correct_answer: str,
    explanation: str,
    chunk_ids: list[UUID] = None,
    error_type: str = None,
) -> WrongQuestion:
    """
    添加错题

    Args:
        db: 数据库会话
        user_id: 用户 ID
        quiz_id: 测验 ID
        question: 题目
        user_answer: 用户答案
        correct_answer: 正确答案
        explanation: 解析
        chunk_ids: 关联的知识块 ID
        error_type: 错误类型

    Returns:
        WrongQuestion
    """
    wrong_question = WrongQuestion(
        user_id=user_id,
        quiz_id=quiz_id,
        question=question,
        user_answer=user_answer,
        correct_answer=correct_answer,
        explanation=explanation,
        chunk_ids=[str(cid) for cid in chunk_ids] if chunk_ids else [],
        error_type=error_type,
        review_count=0,
        mastered=False,
    )

    db.add(wrong_question)
    await db.commit()
    await db.refresh(wrong_question)

    return wrong_question


async def get_wrong_questions(
    db: AsyncSession,
    user_id: UUID,
    mastered: bool = False,
    time_range: dict | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[WrongQuestion]:
    """
    获取错题列表

    Args:
        db: 数据库会话
        user_id: 用户 ID
        mastered: 是否已掌握
        time_range: 时间范围
        limit: 返回数量
        offset: 偏移量

    Returns:
        错题列表
    """
    query = select(WrongQuestion).where(
        WrongQuestion.user_id == user_id,
        WrongQuestion.mastered == mastered,
    )

    if time_range:
        start = time_range.get("start")
        end = time_range.get("end")
        if start:
            query = query.where(WrongQuestion.created_at >= start)
        if end:
            query = query.where(WrongQuestion.created_at <= end)

    query = query.order_by(WrongQuestion.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)

    return list(result.scalars().all())


async def mark_mastered(
    db: AsyncSession,
    wrong_question_id: UUID,
    user_id: UUID,
) -> WrongQuestion | None:
    """
    标记错题已掌握

    Args:
        db: 数据库会话
        wrong_question_id: 错题 ID
        user_id: 用户 ID

    Returns:
        更新后的 WrongQuestion，如果不存在返回 None
    """
    result = await db.execute(
        select(WrongQuestion).where(
            WrongQuestion.id == wrong_question_id,
            WrongQuestion.user_id == user_id,
        ),
    )
    wrong_question = result.scalar_one_or_none()

    if not wrong_question:
        return None

    wrong_question.mastered = True
    wrong_question.last_reviewed_at = datetime.utcnow()
    wrong_question.review_count += 1

    await db.commit()
    await db.refresh(wrong_question)

    return wrong_question


async def increment_review_count(
    db: AsyncSession,
    wrong_question_id: UUID,
    user_id: UUID,
) -> WrongQuestion | None:
    """
    增加复习次数

    Args:
        db: 数据库会话
        wrong_question_id: 错题 ID
        user_id: 用户 ID

    Returns:
        更新后的 WrongQuestion，如果不存在返回 None
    """
    result = await db.execute(
        select(WrongQuestion).where(
            WrongQuestion.id == wrong_question_id,
            WrongQuestion.user_id == user_id,
        ),
    )
    wrong_question = result.scalar_one_or_none()

    if not wrong_question:
        return None

    wrong_question.review_count += 1
    wrong_question.last_reviewed_at = datetime.utcnow()

    await db.commit()
    await db.refresh(wrong_question)

    return wrong_question
