"""Unit tests for gateway review API."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway.app.api.auth import get_user_id_dependency
from gateway.app.api.review import router
from shared.database import get_db


@pytest.fixture
def app(mock_db, user_id):
    app = FastAPI()

    async def override_get_user_id():
        return user_id

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_user_id_dependency] = override_get_user_id
    app.dependency_overrides[get_db] = override_get_db
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _patch_mastery_helpers():
    with (
        patch("gateway.app.api.review.upsert_mastery", new=AsyncMock()),
        patch("gateway.app.api.review.record_daily_stats", new=AsyncMock()),
    ):
        yield


class TestReviewPending:
    def test_pending_no_auth(self):
        """No auth → 401."""
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/review/pending")
        assert resp.status_code == 401

    def test_pending_empty(self, client, mock_db, valid_token):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        resp = client.get(
            "/api/review/pending",
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["pending_count"] == 0

    def test_pending_returns_answer(self, client, mock_db, valid_token):
        from shared.models import ReviewSchedule

        s = ReviewSchedule(
            id=uuid4(),
            chunk_id=None,
            topic="Python 列表",
            answer="正确答案: []\n解析: 列表字面量",
            mastery_score=10.0,
            next_review=datetime.utcnow(),
            interval_days=1.0,
            review_count=0,
            status="active",
            source="quiz",
            reason="wrong",
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [s]
        mock_db.execute.return_value = mock_result

        resp = client.get(
            "/api/review/pending",
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["pending_count"] == 1
        assert data["items"][0]["answer"] == "正确答案: []\n解析: 列表字面量"
        assert data["items"][0]["topic"] == "Python 列表"


class TestReviewSubmit:
    def test_submit_no_auth(self):
        """No auth → 401."""
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/review/submit",
            json={
                "schedule_id": str(uuid4()),
                "result": "good",
            },
        )
        assert resp.status_code == 401

    def test_submit_not_found(self, client, mock_db, valid_token):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        resp = client.post(
            "/api/review/submit",
            json={"schedule_id": str(uuid4()), "result": "good"},
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        assert resp.status_code == 404

    def test_submit_schedules_next_review_in_future(self, client, mock_db, valid_token, user_id):
        """复习提交后 next_review 应按新间隔推迟，而不是立即到期"""
        from shared.models import ReviewSchedule

        s = ReviewSchedule(
            id=uuid4(),
            chunk_id=None,
            user_id=user_id,
            topic="T",
            answer=None,
            mastery_score=50.0,
            next_review=datetime.utcnow() - timedelta(days=1),
            interval_days=1.0,
            ease_factor=2.5,
            review_count=0,
            status="active",
            source="quiz",
            reason="wrong",
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = s
        mock_db.execute.return_value = mock_result
        added = []
        mock_db.add.side_effect = lambda obj: added.append(obj)

        before = datetime.utcnow()
        resp = client.post(
            "/api/review/submit",
            json={"schedule_id": str(s.id), "result": "good"},
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        assert resp.status_code == 200
        assert s.next_review > before
        assert s.review_count == 1
        assert s.interval_days == 2.5  # 1.0 * ef(2.5) * 1.0
        assert len(added) == 1  # review log
        body = resp.json()
        assert body["status"] == "active"

    def test_submit_forgot_resets_interval(self, client, mock_db, valid_token, user_id):
        """记错了(forgot) 等价于直接回答忘记: 间隔重置为 1 天"""
        from shared.models import ReviewSchedule

        s = ReviewSchedule(
            id=uuid4(),
            chunk_id=None,
            user_id=user_id,
            topic="T",
            answer=None,
            mastery_score=50.0,
            next_review=datetime.utcnow() - timedelta(days=1),
            interval_days=5.0,
            ease_factor=2.5,
            review_count=1,
            status="active",
            source="quiz",
            reason="wrong",
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = s
        mock_db.execute.return_value = mock_result
        mock_db.add = MagicMock()

        before = datetime.utcnow()
        resp = client.post(
            "/api/review/submit",
            json={"schedule_id": str(s.id), "result": "forgot"},
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        assert resp.status_code == 200
        assert float(s.interval_days) == 1.0
        assert s.next_review > before
        assert float(s.mastery_score) == 35.0  # 50 - 15
        body = resp.json()
        assert body["status"] == "active"

    def test_submit_with_decimal_values_ok(self, client, mock_db, valid_token, user_id):
        """DB 返回的 Numeric 列是 Decimal，记录日志时必须能兼容(线上 bug 回归)"""
        from decimal import Decimal

        from shared.models import ReviewSchedule

        s = ReviewSchedule(
            id=uuid4(),
            chunk_id=None,
            user_id=user_id,
            topic="T",
            answer=None,
            mastery_score=Decimal("50.00"),
            next_review=datetime.utcnow() - timedelta(days=1),
            interval_days=Decimal("1.00"),
            ease_factor=Decimal("2.50"),
            review_count=0,
            status="active",
            source="quiz",
            reason="wrong",
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = s
        mock_db.execute.return_value = mock_result
        added = []
        mock_db.add.side_effect = lambda obj: added.append(obj)

        resp = client.post(
            "/api/review/submit",
            json={"schedule_id": str(s.id), "result": "good"},
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        assert resp.status_code == 200
        assert float(s.interval_days) == 2.5
        assert len(added) == 1  # review log 纪录成功


class TestReviewStats:
    def test_stats_no_auth(self):
        """No auth → 401."""
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/review/stats")
        assert resp.status_code == 401

    def test_stats_empty(self, client, mock_db, valid_token):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        resp = client.get(
            "/api/review/stats",
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0


class TestArchiveReview:
    def test_archive_no_auth(self):
        """No auth → 401."""
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(f"/api/review/{uuid4()}/archive")
        assert resp.status_code == 401

    def test_archive_not_found(self, client, mock_db, valid_token):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        resp = client.post(
            f"/api/review/{uuid4()}/archive",
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        assert resp.status_code == 404

    def test_archive_sets_paused(self, client, mock_db, valid_token):
        from shared.models import ReviewSchedule

        s = ReviewSchedule(
            id=uuid4(),
            chunk_id=None,
            topic="Python 列表",
            mastery_score=10.0,
            next_review=datetime.utcnow(),
            interval_days=1.0,
            review_count=0,
            status="active",
            source="quiz",
            reason="wrong",
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = s
        mock_db.execute.return_value = mock_result

        resp = client.post(
            f"/api/review/{s.id}/archive",
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        assert resp.status_code == 200
        assert s.status == "paused"
        assert resp.json()["archived"] is True
