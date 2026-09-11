"""掌握度计算"""
from typing import Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import MasteryRecord, ReviewSchedule, Quiz, FeynmanSession


async def calculate_mastery(
    db: AsyncSession,
    user_id: UUID,
    chunk_id: UUID,
    topic: str
) -> MasteryRecord:
    """
    计算知识点掌握度
    
    Args:
        db: 数据库会话
        user_id: 用户 ID
        chunk_id: 知识块 ID
        topic: 主题
    
    Returns:
        MasteryRecord
    """
    # 获取或创建掌握度记录
    result = await db.execute(
        select(MasteryRecord).where(
            MasteryRecord.user_id == user_id,
            MasteryRecord.chunk_id == chunk_id
        )
    )
    record = result.scalar_one_or_none()
    
    if not record:
        record = MasteryRecord(
            user_id=user_id,
            chunk_id=chunk_id,
            topic=topic,
            mastery_score=0.0,
            quiz_accuracy=0.0,
            feynman_score=0.0,
            review_count=0
        )
        db.add(record)
    
    # 获取最近的测验成绩
    quiz_query = (
        select(Quiz)
        .where(Quiz.user_id == user_id, Quiz.status == "completed")
        .order_by(Quiz.completed_at.desc())
        .limit(5)
    )
    quiz_result = await db.execute(quiz_query)
    recent_quizzes = list(quiz_result.scalars().all())
    
    if recent_quizzes:
        avg_score = sum(float(q.score or 0) for q in recent_quizzes) / len(recent_quizzes)
        record.quiz_accuracy = avg_score
    
    # 获取最近的费曼检测成绩
    feynman_query = (
        select(FeynmanSession)
        .where(FeynmanSession.user_id == user_id)
        .order_by(FeynmanSession.created_at.desc())
        .limit(1)
    )
    feynman_result = await db.execute(feynman_query)
    recent_feynman = feynman_result.scalar_one_or_none()
    
    if recent_feynman:
        record.feynman_score = recent_feynman.score or 0
    
    # 获取复习次数
    review_query = select(ReviewSchedule).where(
        ReviewSchedule.user_id == user_id,
        ReviewSchedule.chunk_id == chunk_id
    )
    review_result = await db.execute(review_query)
    review_schedule = review_result.scalar_one_or_none()
    
    if review_schedule:
        record.review_count = review_schedule.review_count
        record.mastery_score = review_schedule.mastery_score
    
    record.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(record)
    
    return record
