"""Gateway API - 费曼 API"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db
from shared.models import ReviewSchedule, Run, Thread
from shared.utils.mastery import record_daily_stats, upsert_mastery
from shared.utils.schedule import compute_next_review_window

from ..services import llm_client
from .auth import get_user_id_dependency

router = APIRouter(prefix="/api/feynman", tags=["feynman"])

EVALUATE_PROMPT = """\
你是一位费曼学习法评估专家。请根据用户与导师的对话历史，评估用户对概念的理解程度。

评估维度：
1. 理解深度 (0-100)：概念是否理解正确
2. 完整性 (0-100)：是否覆盖关键点
3. 清晰度 (0-100)：表达是否清楚

请严格按照以下 JSON 格式返回：
{
    "score": 75,
    "understanding": 80,
    "completeness": 70,
    "clarity": 75,
    "strengths": ["用户理解了..."],
    "weaknesses": ["用户遗漏了..."],
    "suggestions": ["建议复习..."],
    "review_points": [
        {"problem": "用户尚未完全掌握的知识点问题，例如：什么是过拟合？", \
"answer": "该知识点的参考答案/正确解释，用于复习时对照"}
    ]
}

综合评分 = 理解深度 * 0.4 + 完整性 * 0.3 + 清晰度 * 0.3

review_points 的说明：
- 每一个元素是一个复习点，包含 problem（问题/要点）和 answer（参考答案/正确解释）
- review_points 应覆盖用户在对话中遗漏或理解不清晰的要点
- 即使分数达标，只要存在可加强的要点，review_points 也应列出；若用户已完全掌握可返回空数组
- answer 必须是完整、正确、可直接用于复习的参考答案"""


@router.post("/evaluate")
async def evaluate_conversation(
    thread_id: UUID,
    user_id: UUID = Depends(get_user_id_dependency),
    db: AsyncSession = Depends(get_db),
):
    """评估费曼学习对话掌握度"""
    result = await db.execute(
        select(Thread).where(Thread.id == thread_id, Thread.user_id == user_id),
    )
    thread = result.scalar_one_or_none()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    history_result = await db.execute(
        select(Run)
        .where(Run.thread_id == thread_id, Run.status == "completed")
        .order_by(Run.created_at.asc()),
    )
    runs = list(history_result.scalars().all())

    if not runs:
        raise HTTPException(status_code=400, detail="No conversation history")

    conversation = []
    for run in runs:
        user_text = run.input.get("input", "") if isinstance(run.input, dict) else str(run.input)
        conversation.append(f"用户: {user_text}")
        if run.output and isinstance(run.output, dict) and run.output.get("response"):
            conversation.append(f"导师: {run.output['response']}")

    try:
        evaluation = llm_client.chat_json(
            EVALUATE_PROMPT,
            "请评估以下费曼学习对话：\n\n" + "\n".join(conversation),
        )

        evaluation.setdefault("score", 60)
        evaluation.setdefault("understanding", 60)
        evaluation.setdefault("completeness", 60)
        evaluation.setdefault("clarity", 60)
        evaluation.setdefault("strengths", [])
        evaluation.setdefault("weaknesses", [])
        evaluation.setdefault("suggestions", [])
        evaluation.setdefault("review_points", [])

        return evaluation

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)[:200]}") from e


class ReviewItem(BaseModel):
    topic: str
    answer: str | None = None
    source: str | None = "feynman"


class AddToReviewRequest(BaseModel):
    thread_id: UUID
    score: float
    review_items: list[ReviewItem]


@router.post("/add-to-review")
async def add_to_review(
    data: AddToReviewRequest,
    user_id: UUID = Depends(get_user_id_dependency),
    db: AsyncSession = Depends(get_db),
):
    """添加到复习计划（直接写入 gateway 数据库的 review_schedule 表）"""
    result = await db.execute(
        select(Thread).where(Thread.id == data.thread_id, Thread.user_id == user_id),
    )
    thread = result.scalar_one_or_none()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    if not data.review_items:
        raise HTTPException(status_code=400, detail="No review items")

    # 初始间隔: SM-2 默认 1 天, ease factor 2.5
    initial_interval = 1.0
    initial_ease = 2.5
    now = datetime.utcnow()

    created = []
    for item in data.review_items:
        schedule = ReviewSchedule(
            user_id=user_id,
            chunk_id=None,
            topic=item.topic,
            answer=item.answer,
            source=item.source or "feynman",
            next_review=compute_next_review_window(now),
            interval_days=initial_interval,
            ease_factor=initial_ease,
            review_count=0,
            mastery_score=float(data.score),
            status="active",
        )
        db.add(schedule)
        created.append(schedule)

    await db.commit()
    for s in created:
        await db.refresh(s)

    for item in data.review_items:
        await upsert_mastery(
            db,
            user_id,
            item.topic.strip(),
            feynman_score=float(data.score),
        )
    await record_daily_stats(db, user_id, feynman_sessions=1, feynman_avg_score=float(data.score))
    await db.commit()

    return {
        "thread_id": str(data.thread_id),
        "score": data.score,
        "added": len(created),
        "items": [
            {
                "schedule_id": str(s.id),
                "topic": s.topic,
                "answer": s.answer,
                "next_review": s.next_review.isoformat(),
            }
            for s in created
        ],
    }


class FeynmanStart(BaseModel):
    topic: str
    knowledge_context: str | None = None


class FeynmanExplain(BaseModel):
    thread_id: str
    explanation: str
