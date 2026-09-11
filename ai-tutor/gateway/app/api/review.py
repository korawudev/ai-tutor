"""Gateway API - 复习 API（三分支 SM-2 + 会话重试 + 费曼组后验证 + Redis 会话）"""

import json
import os
from datetime import datetime, timedelta
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from review_agent.app.tools.schedule_manager import get_pending_reviews as get_pending_reviews_svc
from review_agent.app.tools.schedule_manager import get_review_stats as get_review_stats_svc
from review_agent.app.tools.schedule_manager import submit_normal_review as svc_submit_normal_review
from review_agent.app.tools.schedule_manager import (
    submit_verification_failed as svc_submit_verification_failed,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db
from shared.models import (
    BatchCompleteSubmit,
    FeynmanVerifyResponse,
    FeynmanVerifySubmit,
    NormalReviewResponse,
    NormalReviewSubmit,
    ReviewBatchStats,
    ReviewItem,
    ReviewListResponse,
    ReviewSchedule,
    SessionSnapshot,
    VerificationFailedSubmit,
    VerificationLog,
)
from shared.utils.mastery import record_daily_stats, upsert_mastery

from ..services import llm_client
from .auth import get_user_id_dependency

router = APIRouter(prefix="/api/review", tags=["review"])

MIN_RESPONSE_TIME_MS = 500
VERIFY_PASS_SCORE = 80

VERIFY_PROMPT = """\
你是一位费曼学习法验证专家。用户针对单个知识点提交了自己的解释，请与参考答案对比评分。

评估维度：
1. 核心概念是否准确
2. 关键点是否覆盖（对照参考答案的关键要素）
3. 表达是否清晰、非复读原文（用自己的话）

请严格按照以下 JSON 格式返回：
{
    "score": 85,
    "strengths": ["核心概念准确：..."],
    "weaknesses": ["遗漏细节：..."],
    "suggestions": ["建议补充：..."],
    "correct_answer": "针对该知识点给出的完整标准答案，2-4 句话，便于用户学习对照"
}

score 为 0-100 整数。strengths/weaknesses/suggestions 为字符串数组，每项一句话。\
correct_answer 必须给出简明准确的标准答案（综合参考答案与你的知识），\
即使用户未作答或答错也要给出。"""


async def _get_redis() -> aioredis.Redis:
    url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    return aioredis.from_url(url, decode_responses=True)


def _session_key(user_id: UUID) -> str:
    return f"review:session:{user_id}"


async def _load_schedule_or_404(
    db: AsyncSession,
    schedule_id: UUID,
    user_id: UUID,
) -> ReviewSchedule:
    result = await db.execute(
        select(ReviewSchedule).where(
            ReviewSchedule.id == schedule_id,
            ReviewSchedule.user_id == user_id,
        ),
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="Review schedule not found")
    return schedule


def _to_review_item(s: ReviewSchedule) -> ReviewItem:
    return ReviewItem(
        schedule_id=s.id,
        chunk_id=s.chunk_id,
        topic=s.topic or "",
        answer=s.answer,
        mastery_score=float(s.mastery_score),
        next_review=s.next_review,
        interval_days=float(s.interval_days),
        review_count=s.review_count,
        status=s.status,
        source=s.source,
        reason=s.reason,
        is_mastered=bool(s.is_mastered),
        correct_streak=s.correct_streak,
    )


@router.get("/pending", response_model=ReviewListResponse)
async def get_pending_reviews(
    limit: int = 20,
    source_type: str | None = None,
    tag_filter: str | None = None,
    user_id: UUID = Depends(get_user_id_dependency),
    db: AsyncSession = Depends(get_db),
):
    """获取待复习内容（可选 source_type=daily|wrong_book|manual，tag_filter 标签过滤）"""
    if source_type not in (None, "daily", "wrong_book", "manual"):
        raise HTTPException(
            status_code=422,
            detail="source_type must be one of: daily, wrong_book, manual",
        )
    schedules = await get_pending_reviews_svc(db, user_id, limit, source_type, tag_filter)

    overdue_q = select(ReviewSchedule).where(
        ReviewSchedule.user_id == user_id,
        ReviewSchedule.status == "active",
        ReviewSchedule.next_review < datetime.utcnow(),
    )
    overdue_count = len((await db.execute(overdue_q)).scalars().all())

    items = [_to_review_item(s) for s in schedules]
    return ReviewListResponse(pending_count=len(items), overdue_count=overdue_count, items=items)


@router.post("/normal", response_model=NormalReviewResponse)
async def submit_normal_review(
    data: NormalReviewSubmit,
    background_tasks: BackgroundTasks,
    user_id: UUID = Depends(get_user_id_dependency),
    db: AsyncSession = Depends(get_db),
):
    """提交正式复习结果（三分支：mastered/vague/forgotten；<500ms 视为无效作答）"""
    if data.response_time_ms < MIN_RESPONSE_TIME_MS:
        raise HTTPException(status_code=400, detail="请仔细思考后再作答")
    result = await svc_submit_normal_review(
        db,
        data.schedule_id,
        user_id,
        data.answer,
        data.response_time_ms,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Review schedule not found")

    schedule = result["schedule"]

    # 后台任务：更新 mastery 与每日统计
    if schedule.topic:
        background_tasks.add_task(
            upsert_mastery,
            db,
            user_id,
            schedule.topic.strip(),
            chunk_id=schedule.chunk_id,
            review_score=float(schedule.mastery_score),
        )
    background_tasks.add_task(record_daily_stats, db, user_id, reviews_completed=1)

    return NormalReviewResponse(
        schedule_id=schedule.id,
        chunk_id=schedule.chunk_id,
        next_review_time=result["next_review_time"],
        ease_factor=result["ease_factor"],
        correct_streak=result["correct_streak"],
        is_mastered=result["is_mastered"],
        need_session_retry=result["need_session_retry"],
        retry_reason=result["retry_reason"],
        mastery_change=result["mastery_change"],
    )


@router.post("/verification-failed", response_model=NormalReviewResponse)
async def submit_verification_failed(
    data: VerificationFailedSubmit,
    background_tasks: BackgroundTasks,
    user_id: UUID = Depends(get_user_id_dependency),
    db: AsyncSession = Depends(get_db),
):
    """组后验证失败：轻微下调 ease_factor，不重置间隔"""
    result = await svc_submit_verification_failed(
        db,
        user_id,
        data.chunk_id,
        data.schedule_id,
        data.response_time_ms,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Review schedule not found")

    schedule = result["schedule"]

    return NormalReviewResponse(
        schedule_id=schedule.id,
        chunk_id=schedule.chunk_id,
        next_review_time=schedule.next_review,
        ease_factor=float(schedule.ease_factor),
        correct_streak=schedule.correct_streak,
        is_mastered=bool(schedule.is_mastered),
        need_session_retry=False,
        retry_reason=None,
        mastery_change=result["mastery_change"],
    )


@router.get("/stats")
async def review_stats(
    user_id: UUID = Depends(get_user_id_dependency),
    db: AsyncSession = Depends(get_db),
):
    """获取复习统计"""
    return await get_review_stats_svc(db, user_id)


@router.post("/{schedule_id}/archive")
async def archive_review(
    schedule_id: UUID,
    user_id: UUID = Depends(get_user_id_dependency),
    db: AsyncSession = Depends(get_db),
):
    """软删除复习计划项: 置为 paused, 不再出现在待复习列表."""
    result = await db.execute(
        select(ReviewSchedule).where(
            ReviewSchedule.id == schedule_id,
            ReviewSchedule.user_id == user_id,
        ),
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="Review schedule not found")

    schedule.status = "paused"
    await db.commit()
    return {"archived": True, "schedule_id": str(schedule.id)}


@router.post("/{schedule_id}/master")
async def mark_mastered(
    schedule_id: UUID,
    user_id: UUID = Depends(get_user_id_dependency),
    db: AsyncSession = Depends(get_db),
):
    """手动标记掌握：直接置 is_mastered=true，移出待复习池"""
    result = await db.execute(
        select(ReviewSchedule).where(
            ReviewSchedule.id == schedule_id,
            ReviewSchedule.user_id == user_id,
        ),
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="Review schedule not found")

    schedule.is_mastered = 1
    schedule.status = "mastered"
    schedule.correct_streak = 3
    schedule.mastery_score = 100.0
    schedule.ease_factor = 2.5
    schedule.next_review = datetime.utcnow() + timedelta(days=3650)  # 10年

    await db.commit()
    return {"mastered": True, "schedule_id": str(schedule.id)}


@router.post("/feynman-verify", response_model=FeynmanVerifyResponse)
async def feynman_verify(
    data: FeynmanVerifySubmit,
    user_id: UUID = Depends(get_user_id_dependency),
    db: AsyncSession = Depends(get_db),
):
    """组后验证费曼评分：AI 对用户解释打分（>=80 通过）。仅记录 VerificationLog，不改 memory 状态"""
    schedule = await _load_schedule_or_404(db, data.schedule_id, user_id)

    user_content = (
        f"知识点：{schedule.topic}\n"
        f"参考答案：{schedule.answer or '（无）'}\n"
        f"用户解释：{data.explanation}"
    )
    try:
        evaluation = llm_client.chat_json(VERIFY_PROMPT, user_content)
        score = int(evaluation.get("score", 60))
        score = max(0, min(100, score))
        passed = score >= VERIFY_PASS_SCORE
        strengths = evaluation.get("strengths", [])
        weaknesses = evaluation.get("weaknesses", [])
        suggestions = evaluation.get("suggestions", [])
        correct_answer = evaluation.get("correct_answer") or schedule.answer or "（暂无标准答案）"
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM 评分失败: {str(e)[:200]}") from e

    log = VerificationLog(
        user_id=user_id,
        chunk_id=schedule.chunk_id,
        schedule_id=schedule.id,
        verification_type="feynman",
        user_answer=data.explanation,
        ai_score=score,
        passed=1 if passed else 0,
    )
    db.add(log)
    await db.commit()

    return FeynmanVerifyResponse(
        schedule_id=schedule.id,
        score=score,
        passed=passed,
        strengths=strengths,
        weaknesses=weaknesses,
        suggestions=suggestions,
        correct_answer=correct_answer,
    )


@router.get("/session")
async def load_session(
    user_id: UUID = Depends(get_user_id_dependency),
):
    """恢复复习会话快照"""
    redis = await _get_redis()
    raw = await redis.get(_session_key(user_id))
    await redis.aclose()
    if not raw:
        raise HTTPException(status_code=404, detail="No saved session")
    return json.loads(raw)


@router.post("/session")
async def save_session(
    data: SessionSnapshot,
    user_id: UUID = Depends(get_user_id_dependency),
):
    """保存复习会话快照（TTL 24h）"""
    redis = await _get_redis()
    await redis.set(_session_key(user_id), data.model_dump_json(), ex=86400)
    await redis.aclose()
    return {"saved": True}


@router.delete("/session")
async def clear_session(
    user_id: UUID = Depends(get_user_id_dependency),
):
    """清除复习会话快照（正常完成/主动退出/用户拒绝恢复）"""
    redis = await _get_redis()
    await redis.delete(_session_key(user_id))
    await redis.aclose()
    return {"cleared": True}


@router.post("/batch-complete")
async def batch_complete(
    data: BatchCompleteSubmit,
    user_id: UUID = Depends(get_user_id_dependency),
    db: AsyncSession = Depends(get_db),
):
    """复习组完成埋点上报（v1.0 只写不读）"""
    stats = ReviewBatchStats(
        user_id=user_id,
        batch_id=data.batch_id,
        total_count=data.total_count,
        mastered_count=data.mastered_count,
        retry_count=data.retry_count,
        duration_sec=data.duration_sec,
        avg_response_ms=data.avg_response_ms,
    )
    db.add(stats)
    await db.commit()
    return {"recorded": True, "batch_id": data.batch_id}
