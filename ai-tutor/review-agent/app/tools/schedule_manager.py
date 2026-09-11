"""复习调度管理 - 支持三分支 SM-2 与会话重试"""
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import (
    ReviewSchedule, ReviewLog, VerificationLog, Chunk,
    NormalReviewAnswer
)
from .spaced_repetition import (
    calculate_next_review, 
    get_initial_interval,
    NormalReviewAnswer
)


async def submit_normal_review(
    db: AsyncSession,
    schedule_id: UUID,
    user_id: UUID,
    answer: str,
    response_time_ms: int = 0
) -> Optional[dict]:
    """
    提交正式复习结果
    
    Args:
        db: 数据库会话
        schedule_id: 调度 ID
        user_id: 用户 ID
        answer: 作答结果 (mastered/vague/forgotten)
        response_time_ms: 反应时间毫秒
        
    Returns:
        包含更新后状态和 need_session_retry 标记的字典
    """
    # 解析答案
    try:
        answer_enum = NormalReviewAnswer(answer)
    except ValueError:
        # 兼容旧版本
        mapping = {"easy": "mastered", "good": "mastered", "hard": "vague", "forgot": "forgotten"}
        answer_enum = NormalReviewAnswer(mapping.get(answer, "forgotten"))
    
    # 获取调度
    query = select(ReviewSchedule).where(
        ReviewSchedule.id == schedule_id,
        ReviewSchedule.user_id == user_id
    )
    result_obj = await db.execute(query)
    schedule = result_obj.scalar_one_or_none()
    
    if not schedule:
        return None
    
    # 计算新状态
    new_state = calculate_next_review(
        NormalReviewAnswer(answer),
        float(schedule.interval_days),
        float(schedule.ease_factor),
        float(schedule.mastery_score),
        schedule.correct_streak
    )
    
    old_mastery = float(schedule.mastery_score)
    old_ease = float(schedule.ease_factor)
    old_interval = float(schedule.interval_days)
    old_streak = schedule.correct_streak
    
    # 记录日志
    log = ReviewLog(
        user_id=user_id,
        schedule_id=schedule_id,
        chunk_id=schedule.chunk_id,
        result=answer,
        old_interval=schedule.interval_days,
        new_interval=new_state.new_interval,
        ease_factor_change=new_state.ease_factor - float(schedule.ease_factor),
        old_ease_factor=schedule.ease_factor,
        new_ease_factor=new_state.ease_factor,
        old_mastery_score=schedule.mastery_score,
        new_mastery_score=new_state.mastery_score,
        correct_streak=new_state.correct_streak,
        answer_type="normal_review",
        response_time_ms=response_time_ms
    )
    db.add(log)
    
    # 更新调度
    schedule.interval_days = new_state.new_interval
    schedule.ease_factor = new_state.ease_factor
    schedule.mastery_score = new_state.mastery_score
    schedule.correct_streak = new_state.correct_streak
    schedule.status = new_state.status
    schedule.is_mastered = 1 if new_state.status == "mastered" else 0
    schedule.next_review = datetime.utcnow() + timedelta(days=new_state.new_interval)
    schedule.last_reviewed_at = datetime.utcnow()
    schedule.review_count += 1
    schedule.last_normal_answer = answer
    
    await db.commit()
    await db.refresh(schedule)
    
    # 计算掌握度变化
    mastery_change = {
        "old": old_mastery,
        "new": new_state.mastery_score,
        "delta": new_state.mastery_score - old_mastery
    }
    
    return {
        "schedule": schedule,
        "next_review_time": schedule.next_review,
        "ease_factor": float(schedule.ease_factor),
        "correct_streak": schedule.correct_streak,
        "is_mastered": bool(schedule.is_mastered),
        "need_session_retry": new_state.need_session_retry,
        "retry_reason": new_state.retry_reason,
        "mastery_change": mastery_change
    }


async def submit_verification_failed(
    db: AsyncSession,
    user_id: UUID,
    chunk_id: UUID,
    schedule_id: UUID,
    response_time_ms: int = 0
) -> Optional[dict]:
    """
    组后验证失败：轻微下调 ease_factor，next_review 置为 now 重新加入全局待复习池（产品文档 §10.3）
    
    Args:
        db: 数据库会话
        user_id: 用户 ID
        chunk_id: 知识块 ID
        schedule_id: 调度 ID
        response_time_ms: 反应时间毫秒
        
    Returns:
        更新后的状态字典
    """
    query = select(ReviewSchedule).where(
        ReviewSchedule.id == schedule_id,
        ReviewSchedule.user_id == user_id
    )
    result_obj = await db.execute(query)
    schedule = result_obj.scalar_one_or_none()
    
    if not schedule:
        return None
    
    # 轻微降级：ease_factor -0.05，mastery_score -3，next_review=now 重新入池
    new_ease = max(float(schedule.ease_factor) - 0.05, 1.3)
    new_mastery = max(float(schedule.mastery_score) - 3, 0)
    
    old_mastery = float(schedule.mastery_score)
    old_ease = float(schedule.ease_factor)
    
    # 记录复习日志
    log = ReviewLog(
        user_id=user_id,
        schedule_id=schedule_id,
        chunk_id=chunk_id,
        result="verification_failed",
        old_interval=schedule.interval_days,
        new_interval=schedule.interval_days,
        ease_factor_change=new_ease - float(schedule.ease_factor),
        old_ease_factor=schedule.ease_factor,
        new_ease_factor=new_ease,
        old_mastery_score=schedule.mastery_score,
        new_mastery_score=new_mastery,
        correct_streak=schedule.correct_streak,
        answer_type="verification_failed"
    )
    db.add(log)
    
    # 记录组后验证日志（feynman 类型，验证失败）
    verification_log = VerificationLog(
        user_id=user_id,
        chunk_id=chunk_id,
        schedule_id=schedule_id,
        verification_type="feynman",
        passed=0
    )
    db.add(verification_log)
    
    # 更新调度：间隔不变，next_review 置 now → 立刻回到全局待复习池
    schedule.ease_factor = new_ease
    schedule.mastery_score = new_mastery
    schedule.status = "active"
    schedule.is_mastered = 0
    schedule.next_review = datetime.utcnow()
    
    await db.commit()
    await db.refresh(schedule)
    
    mastery_change = {
        "old": old_mastery,
        "new": new_mastery,
        "delta": new_mastery - old_mastery
    }
    
    return {
        "schedule": schedule,
        "mastery_change": mastery_change
    }


async def get_pending_reviews(
    db: AsyncSession,
    user_id: UUID,
    limit: int = 10,
    source_type: Optional[str] = None,
    tag_filter: Optional[str] = None
) -> List[ReviewSchedule]:
    """
    获取待复习内容
    
    Args:
        db: 数据库会话
        user_id: 用户 ID
        limit: 返回数量
        source_type: 池来源过滤 daily(默认全量)/wrong_book/manual
        tag_filter: 标签过滤（仅对有 chunk_id 的记录生效）
        
    Returns:
        待复习列表
    """
    query = (
        select(ReviewSchedule)
        .where(
            ReviewSchedule.user_id == user_id,
            ReviewSchedule.status == "active",
            ReviewSchedule.next_review <= datetime.utcnow()
        )
    )
    
    if source_type == "wrong_book":
        query = query.where(ReviewSchedule.source == "quiz", ReviewSchedule.reason == "wrong")
    elif source_type == "manual":
        query = query.where(ReviewSchedule.source == "manual")
    
    if tag_filter:
        query = query.join(Chunk, ReviewSchedule.chunk_id == Chunk.id).where(
            Chunk.tags.contains([tag_filter])
        )
    
    query = query.order_by(ReviewSchedule.next_review.asc()).limit(limit)
    
    result = await db.execute(query)
    return list(result.scalars().all())


async def create_review_schedule(
    db: AsyncSession,
    user_id: UUID,
    chunk_id: UUID,
    topic: str,
    source: str = "feynman",
    reason: str = None
) -> ReviewSchedule:
    """
    创建复习调度
    """
    interval, ease_factor = get_initial_interval()
    
    schedule = ReviewSchedule(
        user_id=user_id,
        chunk_id=chunk_id,
        topic=topic,
        source=source,
        reason=reason,
        next_review=datetime.utcnow() + timedelta(days=interval),
        interval_days=interval,
        ease_factor=ease_factor,
        review_count=0,
        mastery_score=0.0,
        correct_streak=0,
        is_mastered=0,
        status="active"
    )
    
    db.add(schedule)
    await db.commit()
    await db.refresh(schedule)
    
    return schedule


async def get_review_stats(
    db: AsyncSession,
    user_id: UUID
) -> dict:
    """
    获取复习统计
    """
    # 总数
    total_query = select(ReviewSchedule).where(
        ReviewSchedule.user_id == user_id,
        ReviewSchedule.status == "active"
    )
    total_result = await db.execute(total_query)
    total = len(list(total_result.scalars().all()))
    
    # 待复习
    pending_query = select(ReviewSchedule).where(
        ReviewSchedule.user_id == user_id,
        ReviewSchedule.status == "active",
        ReviewSchedule.next_review <= datetime.utcnow()
    )
    pending_result = await db.execute(pending_query)
    pending = len(list(pending_result.scalars().all()))
    
    # 已掌握
    mastered_query = select(ReviewSchedule).where(
        ReviewSchedule.user_id == user_id,
        ReviewSchedule.status == "mastered"
    )
    mastered_result = await db.execute(mastered_query)
    mastered = len(list(mastered_result.scalars().all()))
    
    return {
        "total": total,
        "pending": pending,
        "mastered": mastered,
        "active": total - mastered
    }
