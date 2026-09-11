"""Unit tests for shared.utils.mastery helpers."""
import pytest
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from shared.utils.mastery import (
    local_date_to_utc_window,
    resolve_chunk_for_topic,
    upsert_mastery,
    record_daily_stats,
    _merge_mastery,
)


class TestLocalDateToUtcWindow:
    def test_shanghai_day_maps_to_previous_utc_day(self):
        start, end = local_date_to_utc_window(date(2026, 9, 8))
        assert start == datetime(2026, 9, 7, 16, 0)  # 上海 09-08 00:00 == UTC 09-07 16:00
        assert end == datetime(2026, 9, 8, 16, 0)

    def test_window_is_24h(self):
        start, end = local_date_to_utc_window(date(2026, 1, 1))
        assert (end - start).total_seconds() == 86400


class TestResolveChunkForTopic:
    async def test_returns_matching_chunk(self):
        db = AsyncMock()
        db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=uuid4()))

        chunk_id = await resolve_chunk_for_topic(db, uuid4(), "神经网络")
        assert chunk_id is not None

    async def test_blank_topic_returns_none(self):
        db = AsyncMock()
        assert await resolve_chunk_for_topic(db, uuid4(), "") is None
        assert await resolve_chunk_for_topic(db, uuid4(), None) is None


class TestMergeMastery:
    def test_single_signal_returns_that_signal(self):
        assert _merge_mastery(80, None, None, has_quiz=True) == 80
        assert _merge_mastery(None, 60, None, has_feynman=True) == 60
        assert _merge_mastery(None, None, 40, has_review=True) == 40

    def test_weights_sum_to_one(self):
        # 80*0.5 + 60*0.15 + 40*0.35 = 40 + 9 + 14 = 63
        assert _merge_mastery(80, 60, 40, has_quiz=True, has_feynman=True, has_review=True) == 63.0

    def test_no_signals_returns_zero(self):
        assert _merge_mastery(None, None, None) == 0.0

    def test_quiz_plus_review_normalized_by_active_weights(self):
        # (100*0.5 + 15*0.35) / (0.5+0.35) = 55.25 / 0.85 = 65.0
        assert _merge_mastery(100, None, 15, has_quiz=True, has_review=True) == 65.0

    def test_inactive_signal_ignored(self):
        # quiz_accuracy 未激活(无 last_quiz_at)时不计入，仅 review 生效
        assert _merge_mastery(100, None, 40, has_review=True) == 40


class TestUpsertMastery:
    async def test_skips_when_no_chunk_resolved(self):
        db = AsyncMock()
        db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        assert await upsert_mastery(db, uuid4(), "无匹配知识点", quiz_accuracy=90) is False

    async def test_creates_new_record(self):
        db = AsyncMock()
        db.add = MagicMock()
        chunk_id = uuid4()
        db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        added = []
        db.add.side_effect = lambda obj: added.append(obj)

        created = await upsert_mastery(db, uuid4(), "梯度下降", chunk_id=chunk_id, quiz_accuracy=80)
        assert created is True
        assert len(added) == 1
        assert added[0].quiz_accuracy == 80
        assert added[0].mastery_score == 80

    async def test_updates_existing_record(self):
        from shared.models import MasteryRecord
        db = AsyncMock()
        chunk_id = uuid4()
        existing = MasteryRecord(chunk_id=chunk_id, review_count=0)
        db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=existing))

        await upsert_mastery(db, uuid4(), "梯度下降", chunk_id=chunk_id, quiz_accuracy=100)
        assert existing.quiz_accuracy == 100
        assert existing.review_count == 0  # quiz 不增加 review_count

    async def test_review_after_quiz_merges_not_overwrites(self):
        from shared.models import MasteryRecord
        db = AsyncMock()
        chunk_id = uuid4()
        existing = MasteryRecord(chunk_id=chunk_id, quiz_accuracy=100, review_count=0)
        existing.last_quiz_at = datetime.utcnow()
        db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=existing))

        await upsert_mastery(db, uuid4(), "梯度下降", chunk_id=chunk_id, review_score=15)
        # (100*0.5 + 15*0.35) / (0.5+0.35) = 65.0
        assert existing.mastery_score == 65.0
        assert existing.quiz_accuracy == 100  # quiz 信号保留
        assert existing.review_count == 1


class TestRecordDailyStats:
    async def _setup(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        added = []
        db.add.side_effect = lambda obj: added.append(obj)
        return db, added

    async def test_creates_stats_with_increments(self):
        db, added = await self._setup()
        day = date(2026, 9, 8)
        await record_daily_stats(db, uuid4(), day=day, quizzes_taken=2, reviews_completed=1)
        assert len(added) == 1
        assert added[0].quizzes_taken == 2
        assert added[0].reviews_completed == 1

    async def test_avg_score_weighted(self):
        from shared.models import LearningStats
        db = AsyncMock()
        stats = LearningStats(quizzes_taken=1, quiz_avg_score=60)
        db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=stats))

        await record_daily_stats(db, uuid4(), day=date(2026, 9, 8), quizzes_taken=1, quiz_avg_score=80)
        assert stats.quiz_avg_score == 70  # (60*1 + 80*1) / 2