"""Unit tests for progress-agent tools."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


class TestCalculateMastery:
    @pytest.mark.asyncio
    async def test_creates_new_record(self, progress_modules, mock_db, user_id):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_quiz_result = MagicMock()
        mock_quiz_result.scalars.return_value.all.return_value = []
        mock_feynman_result = MagicMock()
        mock_feynman_result.scalar_one_or_none.return_value = None
        mock_review_result = MagicMock()
        mock_review_result.scalar_one_or_none.return_value = None
        mock_db.execute.side_effect = [
            mock_result,
            mock_quiz_result,
            mock_feynman_result,
            mock_review_result,
        ]
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        chunk_id = uuid4()
        await progress_modules.calculate_mastery(mock_db, user_id, chunk_id, "Python")
        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_updates_existing_record(self, progress_modules, mock_db, user_id):
        existing = MagicMock()
        existing.id = uuid4()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_quiz_result = MagicMock()
        mock_quiz_result.scalars.return_value.all.return_value = []
        mock_feynman_result = MagicMock()
        mock_feynman_result.scalar_one_or_none.return_value = None
        mock_review_result = MagicMock()
        mock_review_result.scalar_one_or_none.return_value = None
        mock_db.execute.side_effect = [
            mock_result,
            mock_quiz_result,
            mock_feynman_result,
            mock_review_result,
        ]
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        await progress_modules.calculate_mastery(mock_db, user_id, uuid4(), "Python")
        mock_db.add.assert_not_called()


class TestDashboardData:
    @pytest.mark.asyncio
    async def test_empty_dashboard(self, progress_modules, mock_db, user_id):
        mock_scalar = MagicMock()
        mock_scalar.scalar.return_value = 0
        mock_db.execute.return_value = mock_scalar

        data = await progress_modules.get_dashboard_data(mock_db, user_id)
        assert "summary" in data
        assert "trend" in data
        assert data["summary"]["total_documents"] == 0
