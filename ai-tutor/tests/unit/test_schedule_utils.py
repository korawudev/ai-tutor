"""Unit tests for shared.utils.schedule scheduling helpers."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from shared.utils.schedule import compute_next_review_window

_SH = ZoneInfo("Asia/Shanghai")


def _utc(y, mo, d, h, mi=0, s=0):
    return datetime(y, mo, d, h, mi, s, tzinfo=ZoneInfo("UTC")).replace(tzinfo=None)


def _local_to_utc(y, mo, d, h, mi=0):
    """本地(Asia/Shanghai)墙钟时间 → UTC naive."""
    return datetime(y, mo, d, h, mi, tzinfo=_SH).astimezone(ZoneInfo("UTC")).replace(tzinfo=None)


class TestComputeNextReviewWindow:
    def test_before_evening_schedules_tonight_18(self):
        now = _local_to_utc(2026, 9, 7, 10, 0)  # 本地 10:00
        assert compute_next_review_window(now) == _utc(2026, 9, 7, 10, 0)  # 本地 18:00 == UTC 10:00

    def test_exactly_evening_schedules_tomorrow_08(self):
        now = _local_to_utc(2026, 9, 7, 18, 0)  # 本地 18:00
        assert compute_next_review_window(now) == _utc(2026, 9, 8, 0, 0)  # 次日本地 08:00 == UTC 00:00

    def test_after_evening_schedules_tomorrow_08(self):
        now = _local_to_utc(2026, 9, 7, 23, 0)  # 本地 23:00
        assert compute_next_review_window(now) == _utc(2026, 9, 8, 0, 0)

    def test_null_now_uses_current_time(self):
        # 不抛异常且返回未来时间
        result = compute_next_review_window()
        assert result > datetime.utcnow() - timedelta(days=1)
