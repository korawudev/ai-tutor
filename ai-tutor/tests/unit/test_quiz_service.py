"""Tests for quiz-agent quiz_service."""
import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock


class TestCalculateMasteryChange:
    def test_perfect_score(self, quiz_service_modules):
        result = quiz_service_modules._calculate_mastery_change(5, 5)
        assert result == 10.0

    def test_good_score(self, quiz_service_modules):
        result = quiz_service_modules._calculate_mastery_change(4, 5)
        assert result == 5.0

    def test_average_score(self, quiz_service_modules):
        result = quiz_service_modules._calculate_mastery_change(3, 5)
        assert result == 0.0

    def test_poor_score(self, quiz_service_modules):
        result = quiz_service_modules._calculate_mastery_change(2, 5)
        assert result == -5.0

    def test_very_poor_score(self, quiz_service_modules):
        result = quiz_service_modules._calculate_mastery_change(1, 5)
        assert result == -10.0

    def test_zero_total(self, quiz_service_modules):
        result = quiz_service_modules._calculate_mastery_change(0, 0)
        assert result == 0.0


class TestGetKnowledgeContext:
    @pytest.mark.asyncio
    async def test_topic_scope(self, quiz_service_modules):
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [MagicMock(content="Python classes")]
        db.execute.return_value = mock_result
        result = await quiz_service_modules._get_knowledge_context(
            db, uuid4(), "topic", "Python", None
        )
        assert "Python classes" in result

    @pytest.mark.asyncio
    async def test_time_range_scope(self, quiz_service_modules):
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [MagicMock(content="Recent content")]
        db.execute.return_value = mock_result
        result = await quiz_service_modules._get_knowledge_context(
            db, uuid4(), "time_range", None, {"start": "2024-01-01", "end": "2024-12-31"}
        )
        assert "Recent content" in result

    @pytest.mark.asyncio
    async def test_wrong_review_scope_empty(self, quiz_service_modules):
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute.return_value = mock_result
        result = await quiz_service_modules._get_knowledge_context(
            db, uuid4(), "wrong_review", None, None
        )
        assert "通用编程知识" in result

    @pytest.mark.asyncio
    async def test_fallback(self, quiz_service_modules):
        db = AsyncMock()
        result = await quiz_service_modules._get_knowledge_context(
            db, uuid4(), "unknown", None, None
        )
        assert "通用编程知识" in result
