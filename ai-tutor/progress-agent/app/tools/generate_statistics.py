"""统计生成"""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import Document, LearningStats, MasteryRecord


async def get_dashboard_data(
    db: AsyncSession,
    user_id: UUID,
) -> dict[str, Any]:
    """
    获取仪表盘数据

    Args:
        db: 数据库会话
        user_id: 用户 ID

    Returns:
        仪表盘数据
    """
    # 总文档数
    doc_query = select(func.count(Document.id)).where(
        Document.user_id == user_id,
        Document.deleted_at.is_(None),
    )
    doc_result = await db.execute(doc_query)
    total_documents = doc_result.scalar() or 0

    # 总知识点数
    mastery_query = select(func.count(MasteryRecord.id)).where(
        MasteryRecord.user_id == user_id,
    )
    mastery_result = await db.execute(mastery_query)
    total_concepts = mastery_result.scalar() or 0

    # 已掌握知识点数
    mastered_query = select(func.count(MasteryRecord.id)).where(
        MasteryRecord.user_id == user_id,
        MasteryRecord.mastery_score >= 90,
    )
    mastered_result = await db.execute(mastered_query)
    mastered_concepts = mastered_result.scalar() or 0

    # 平均掌握度
    avg_query = select(func.avg(MasteryRecord.mastery_score)).where(
        MasteryRecord.user_id == user_id,
    )
    avg_result = await db.execute(avg_query)
    avg_mastery = avg_result.scalar() or 0

    # 今日统计
    today = datetime.utcnow().date()
    today_stats = await _get_daily_stats(db, user_id, today)

    # 最近 7 天趋势
    trend = []
    for i in range(6, -1, -1):
        date = today - timedelta(days=i)
        stats = await _get_daily_stats(db, user_id, date)
        trend.append(
            {
                "date": date.isoformat(),
                "score": stats.get("quiz_avg_score", 0),
            },
        )

    return {
        "summary": {
            "total_documents": total_documents,
            "total_concepts": total_concepts,
            "mastered_concepts": mastered_concepts,
            "mastery_rate": (mastered_concepts / total_concepts * 100) if total_concepts > 0 else 0,
            "average_mastery": float(avg_mastery),
        },
        "today": today_stats,
        "trend": trend,
    }


async def _get_daily_stats(
    db: AsyncSession,
    user_id: UUID,
    date,
) -> dict[str, Any]:
    """获取每日统计"""
    query = select(LearningStats).where(
        LearningStats.user_id == user_id,
        LearningStats.date == date,
    )
    result = await db.execute(query)
    stats = result.scalar_one_or_none()

    if stats:
        return {
            "documents_read": stats.documents_read,
            "quizzes_taken": stats.quizzes_taken,
            "quiz_avg_score": float(stats.quiz_avg_score or 0),
            "feynman_sessions": stats.feynman_sessions,
            "feynman_avg_score": float(stats.feynman_avg_score or 0),
            "reviews_completed": stats.reviews_completed,
            "time_spent_minutes": stats.total_time_seconds // 60,
        }

    return {
        "documents_read": 0,
        "quizzes_taken": 0,
        "quiz_avg_score": 0,
        "feynman_sessions": 0,
        "feynman_avg_score": 0,
        "reviews_completed": 0,
        "time_spent_minutes": 0,
    }
