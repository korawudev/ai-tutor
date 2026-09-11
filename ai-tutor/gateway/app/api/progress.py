"""Gateway API - 进度 API"""
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import Document, MasteryRecord, Quiz, FeynmanSession, LearningStats
from shared.database import get_db
from shared.utils.mastery import local_date_to_utc_window
from .auth import get_user_id_dependency
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

router = APIRouter(prefix="/api/progress", tags=["progress"])

_LOCAL_TZ = ZoneInfo("Asia/Shanghai")


@router.get("/dashboard")
async def dashboard(
    user_id: UUID = Depends(get_user_id_dependency),
    db: AsyncSession = Depends(get_db)
):
    """获取仪表盘数据"""
    today = datetime.now(_LOCAL_TZ).date()

    # Counts
    doc_count = (await db.execute(select(func.count(Document.id)).where(Document.user_id == user_id, Document.deleted_at.is_(None)))).scalar() or 0
    concept_count = (await db.execute(select(func.count(MasteryRecord.id)).where(MasteryRecord.user_id == user_id))).scalar() or 0
    mastered_count = (await db.execute(select(func.count(MasteryRecord.id)).where(MasteryRecord.user_id == user_id, MasteryRecord.mastery_score >= 90))).scalar() or 0
    avg_mastery = (await db.execute(select(func.avg(MasteryRecord.mastery_score)).where(MasteryRecord.user_id == user_id))).scalar() or 0

    # Today from LearningStats
    today_stats = (await db.execute(
        select(LearningStats).where(LearningStats.user_id == user_id, LearningStats.date == today)
    )).scalar_one_or_none()

    # Trend (last 7 local days): average mastery of records updated that day
    trend = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        start, end = local_date_to_utc_window(d)
        day_avg = (await db.execute(
            select(func.avg(MasteryRecord.mastery_score)).where(
                MasteryRecord.user_id == user_id,
                MasteryRecord.updated_at >= start,
                MasteryRecord.updated_at < end,
            )
        )).scalar() or 0
        trend.append({"date": d.isoformat(), "score": float(day_avg)})

    return {
        "summary": {
            "total_documents": doc_count,
            "total_concepts": concept_count,
            "mastered_concepts": mastered_count,
            "mastery_rate": (mastered_count / concept_count * 100) if concept_count > 0 else 0,
            "average_mastery": float(avg_mastery),
        },
        "today": {
            "documents_read": today_stats.documents_read if today_stats else 0,
            "quizzes_taken": today_stats.quizzes_taken if today_stats else 0,
            "quiz_avg_score": float(today_stats.quiz_avg_score) if today_stats and today_stats.quiz_avg_score is not None else 0,
            "feynman_sessions": today_stats.feynman_sessions if today_stats else 0,
            "feynman_avg_score": float(today_stats.feynman_avg_score) if today_stats and today_stats.feynman_avg_score is not None else 0,
            "reviews_completed": today_stats.reviews_completed if today_stats else 0,
            "time_spent_minutes": (today_stats.total_time_seconds or 0) // 60 if today_stats else 0,
        },
        "trend": trend,
    }


@router.get("/mastery")
async def mastery_list(
    user_id: UUID = Depends(get_user_id_dependency),
    db: AsyncSession = Depends(get_db)
):
    """获取掌握度列表"""
    result = await db.execute(
        select(MasteryRecord)
        .where(MasteryRecord.user_id == user_id)
        .order_by(MasteryRecord.mastery_score.desc())
        .limit(100)
    )
    records = result.scalars().all()
    return [
        {
            "id": str(r.id), "chunk_id": str(r.chunk_id), "topic": r.topic,
            "mastery_score": float(r.mastery_score), "quiz_accuracy": float(r.quiz_accuracy),
            "feynman_score": float(r.feynman_score), "review_count": r.review_count,
            "updated_at": r.updated_at.isoformat() if r.updated_at else "",
        }
        for r in records
    ]