"""Tests for review-agent schedule_manager."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from shared.models import ReviewSchedule


@pytest.fixture
def db():
    return AsyncMock()


class TestGetPendingReviews:
    @pytest.mark.asyncio
    async def test_returns_pending(self, db, review_schedule_modules):
        now = datetime.utcnow()
        schedule = ReviewSchedule(
            id=uuid4(),
            user_id=uuid4(),
            chunk_id=uuid4(),
            topic="T",
            source="feynman",
            next_review=now - timedelta(hours=1),
            interval_days=1,
            ease_factor=2.5,
            review_count=0,
            mastery_score=50.0,
            status="active",
            created_at=now,
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [schedule]
        db.execute.return_value = mock_result
        result = await review_schedule_modules.get_pending_reviews(db, uuid4())
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_empty(self, db, review_schedule_modules):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute.return_value = mock_result
        result = await review_schedule_modules.get_pending_reviews(db, uuid4())
        assert result == []


class TestCreateReviewSchedule:
    @pytest.mark.asyncio
    async def test_creates_schedule(self, db, review_schedule_modules):
        db.refresh = AsyncMock()
        result = await review_schedule_modules.create_review_schedule(
            db,
            uuid4(),
            uuid4(),
            "Python",
            "feynman",
        )
        db.add.assert_called_once()
        db.commit.assert_called_once()
        assert result.status == "active"


class TestSubmitReviewResult:
    @pytest.mark.asyncio
    async def test_not_found(self, db, review_schedule_modules):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute.return_value = mock_result
        result = await review_schedule_modules.submit_review_result(db, uuid4(), uuid4(), "easy")
        assert result is None

    @pytest.mark.asyncio
    async def test_submits_result(self, db, review_schedule_modules):
        now = datetime.utcnow()
        schedule = ReviewSchedule(
            id=uuid4(),
            user_id=uuid4(),
            chunk_id=uuid4(),
            topic="T",
            source="feynman",
            next_review=now,
            interval_days=1.0,
            ease_factor=2.5,
            review_count=0,
            mastery_score=50.0,
            status="active",
            created_at=now,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = schedule
        db.execute.return_value = mock_result
        db.refresh = AsyncMock()
        result = await review_schedule_modules.submit_review_result(
            db,
            schedule.id,
            schedule.user_id,
            "easy",
        )
        assert result is not None
        assert result.review_count == 1
        db.add.assert_called_once()
        db.commit.assert_called()


class TestGetReviewStats:
    @pytest.mark.asyncio
    async def test_returns_stats(self, db, review_schedule_modules):
        now = datetime.utcnow()
        active = ReviewSchedule(
            id=uuid4(),
            user_id=uuid4(),
            chunk_id=uuid4(),
            topic="T",
            source="feynman",
            next_review=now - timedelta(hours=1),
            interval_days=1,
            ease_factor=2.5,
            review_count=0,
            mastery_score=50.0,
            status="active",
            created_at=now,
        )
        mastered = ReviewSchedule(
            id=uuid4(),
            user_id=uuid4(),
            chunk_id=uuid4(),
            topic="T",
            source="feynman",
            next_review=now + timedelta(days=10),
            interval_days=30,
            ease_factor=2.5,
            review_count=5,
            mastery_score=95.0,
            status="mastered",
            created_at=now,
        )
        call_count = 0

        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1 or call_count == 2:
                result.scalars.return_value.all.return_value = [active]
            else:
                result.scalars.return_value.all.return_value = [mastered]
            return result

        db.execute = mock_execute
        stats = await review_schedule_modules.get_review_stats(db, uuid4())
        assert stats["total"] == 1
        assert stats["mastered"] == 1
