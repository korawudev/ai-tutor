"""Tests for quiz-agent manage_wrong_book."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from shared.models import WrongQuestion


@pytest.fixture
def db():
    return AsyncMock()


class TestGetWrongQuestions:
    @pytest.mark.asyncio
    async def test_with_time_range(self, db, quiz_wrong_book_modules):
        wq = WrongQuestion(
            id=uuid4(),
            user_id=uuid4(),
            quiz_id=uuid4(),
            question={"q": "test"},
            user_answer="A",
            correct_answer="B",
            explanation="exp",
            chunk_ids=[],
            error_type="choice",
            review_count=0,
            mastered=False,
            created_at=datetime.utcnow(),
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [wq]
        db.execute.return_value = mock_result
        result = await quiz_wrong_book_modules.get_wrong_questions(
            db,
            uuid4(),
            time_range={"start": "2024-01-01", "end": "2024-12-31"},
        )
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_empty(self, db, quiz_wrong_book_modules):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute.return_value = mock_result
        result = await quiz_wrong_book_modules.get_wrong_questions(db, uuid4())
        assert result == []


class TestMarkMastered:
    @pytest.mark.asyncio
    async def test_not_found(self, db, quiz_wrong_book_modules):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute.return_value = mock_result
        result = await quiz_wrong_book_modules.mark_mastered(db, uuid4(), uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_marks_mastered(self, db, quiz_wrong_book_modules):
        wq = WrongQuestion(
            id=uuid4(),
            user_id=uuid4(),
            quiz_id=uuid4(),
            question={"q": "test"},
            user_answer="A",
            correct_answer="B",
            explanation="exp",
            chunk_ids=[],
            error_type="choice",
            review_count=2,
            mastered=False,
            created_at=datetime.utcnow(),
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = wq
        db.execute.return_value = mock_result
        db.refresh = AsyncMock()
        result = await quiz_wrong_book_modules.mark_mastered(db, wq.id, wq.user_id)
        assert result.mastered is True
        assert result.review_count == 3


class TestIncrementReviewCount:
    @pytest.mark.asyncio
    async def test_not_found(self, db, quiz_wrong_book_modules):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute.return_value = mock_result
        result = await quiz_wrong_book_modules.increment_review_count(db, uuid4(), uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_increments(self, db, quiz_wrong_book_modules):
        wq = WrongQuestion(
            id=uuid4(),
            user_id=uuid4(),
            quiz_id=uuid4(),
            question={"q": "test"},
            user_answer="A",
            correct_answer="B",
            explanation="exp",
            chunk_ids=[],
            error_type="choice",
            review_count=1,
            mastered=False,
            created_at=datetime.utcnow(),
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = wq
        db.execute.return_value = mock_result
        db.refresh = AsyncMock()
        result = await quiz_wrong_book_modules.increment_review_count(db, wq.id, wq.user_id)
        assert result.review_count == 2
