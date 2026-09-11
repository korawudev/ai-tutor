"""Shared mastery + daily-stats recording helpers.

这些辅助函数在 quiz/review/feynman 流程中落库数据，供进度(progress)仪表盘读取。
- MasteryRecord: 按 (user_id, chunk_id) 唯一，chunk_id 为必填外键，故需先将知识点解析到 chunk。
- LearningStats: 按 (user_id, date) 唯一，使用增量字段累加当日活动。
"""
from datetime import datetime, date as date_type, time as time_type, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import Chunk, Document, MasteryRecord, LearningStats

_LOCAL_TZ = ZoneInfo("Asia/Shanghai")
_UTC = ZoneInfo("UTC")


def local_date_to_utc_window(day):
    """将 UTC+8 自然日转换为 UTC 的 [start, end) 窗口(naive UTC)。

    用户活动按 Asia/Shanghai 日期归属；存储的时间戳是 UTC，因此查询趋势时需先把本地日换算成 UTC 区间。
    """
    start_local = datetime.combine(day, time_type.min, tzinfo=_LOCAL_TZ)
    end_local = start_local + timedelta(days=1)
    return (
        start_local.astimezone(_UTC).replace(tzinfo=None),
        end_local.astimezone(_UTC).replace(tzinfo=None),
    )


async def resolve_chunk_for_topic(db: AsyncSession, user_id, topic: str):
    """将知识点解析为用户文档中最匹配的 chunk_id。

    quiz/review/feynman 携带的是知识点文本而非 chunk_id；MasteryRecord.chunk_id 为必填外键，
    因此按内容模糊匹配用户自己的 chunk；未命中返回 None（调用方跳过掌握度记录，避免伪造外键）。
    """
    if not topic:
        return None
    result = await db.execute(
        select(Chunk.id)
        .join(Document, Chunk.document_id == Document.id)
        .where(
            Document.user_id == user_id,
            Document.deleted_at.is_(None),
            Chunk.content.ilike(f"%{topic.strip()}%"),
        )
        .limit(1)
    )
    return result.scalar_one_or_none()


_SOURCE_WEIGHTS = {"quiz": 0.5, "review": 0.35, "feynman": 0.15}


def _merge_mastery(quiz_accuracy, feynman_score, review_score, *, has_quiz=False, has_feynman=False, has_review=False):
    """加权合并三路信号的掌握度分值（按活跃来源归一化权重）。

    quiz/review 为测验性、权重高；feynman 为讲授性、权重略低。仅计入至少产生过
    一次信号的来源，权重在活跃来源间归一化：例如只有 quiz 时结果即 quiz_accuracy，
    三路齐备时为 0.5*quiz + 0.35*review + 0.15*feynman。
    """
    components = []
    weights = []
    if has_quiz and quiz_accuracy is not None:
        components.append(float(quiz_accuracy))
        weights.append(_SOURCE_WEIGHTS["quiz"])
    if has_review and review_score is not None:
        components.append(float(review_score))
        weights.append(_SOURCE_WEIGHTS["review"])
    if has_feynman and feynman_score is not None:
        components.append(float(feynman_score))
        weights.append(_SOURCE_WEIGHTS["feynman"])
    if not components:
        return 0.0
    return sum(c * w for c, w in zip(components, weights)) / sum(weights)


async def upsert_mastery(
    db: AsyncSession,
    user_id,
    topic: str,
    *,
    chunk_id=None,
    quiz_accuracy=None,
    feynman_score=None,
    review_score=None,
    now=None,
):
    """写入/更新一条掌握度记录。返回是否产生了记录(False 表示未解析到 chunk 而跳过)。

    每次调用只更新本次来源的信号字段与时间戳，mastery_score 始终基于已存的所有
    来源信号(quiz_accuracy/feynman_score/review_score)加权合并，避免上一次信号覆盖。
    """
    now = now or datetime.utcnow()
    if chunk_id is None:
        chunk_id = await resolve_chunk_for_topic(db, user_id, topic)
    if chunk_id is None:
        return False

    result = await db.execute(
        select(MasteryRecord).where(
            MasteryRecord.user_id == user_id,
            MasteryRecord.chunk_id == chunk_id,
        )
    )
    record = result.scalar_one_or_none()

    if record is None:
        record = MasteryRecord(user_id=user_id, chunk_id=chunk_id, topic=topic)
        db.add(record)

    if quiz_accuracy is not None:
        record.quiz_accuracy = round(quiz_accuracy, 2)
        record.last_quiz_at = now
    if feynman_score is not None:
        record.feynman_score = round(feynman_score, 2)
        record.last_feynman_at = now
    if review_score is not None:
        record.review_score = round(review_score, 2)
        record.review_count = (record.review_count or 0) + 1
        record.last_review_at = now

    record.mastery_score = round(
        max(0.0, min(100.0, _merge_mastery(
            record.quiz_accuracy,
            record.feynman_score,
            record.review_score,
            has_quiz=record.last_quiz_at is not None,
            has_feynman=record.last_feynman_at is not None,
            has_review=record.last_review_at is not None,
        ))), 2)

    return True


async def record_daily_stats(db: AsyncSession, user_id, day=None, **increments):
    """按 (user_id, date) 唯一地累加当日学习统计。计数类字段累加；均分字段按次数加权平均。"""
    day = day or datetime.now(_LOCAL_TZ).date()
    result = await db.execute(
        select(LearningStats).where(
            LearningStats.user_id == user_id,
            LearningStats.date == day,
        )
    )
    stats = result.scalar_one_or_none()
    if stats is None:
        stats = LearningStats(user_id=user_id, date=day)
        db.add(stats)

    counter_fields = ("documents_read", "quizzes_taken", "feynman_sessions",
                      "reviews_completed", "new_concepts_learned", "total_time_seconds")
    for field, value in increments.items():
        if value is None:
            continue
        if field in counter_fields:
            setattr(stats, field, (getattr(stats, field) or 0) + int(value))
        elif field in ("quiz_avg_score", "feynman_avg_score"):
            count_field = "quizzes_taken" if field == "quiz_avg_score" else "feynman_sessions"
            inc = int(increments.get(count_field, 1) or 0)
            old_count = (getattr(stats, count_field) or 0) - inc
            old_avg = float(getattr(stats, field) or 0.0)
            new_count = old_count + inc
            setattr(stats, field, round((old_avg * old_count + float(value) * inc) / max(new_count, 1), 2))
