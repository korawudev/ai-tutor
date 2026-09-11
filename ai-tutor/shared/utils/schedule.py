"""Shared scheduling helpers for review next_review computation."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

_LOCAL_TZ = ZoneInfo("Asia/Shanghai")
_UTC = ZoneInfo("UTC")


def compute_next_review_window(now=None):
    """复习节流窗口: 本地当天18:00前加入 → 当天18:00; 18:00后加入 → 次日08:00. 返回UTC(naive)."""
    now = (now or datetime.utcnow()).replace(tzinfo=_UTC)
    local = now.astimezone(_LOCAL_TZ)
    evening = local.replace(hour=18, minute=0, second=0, microsecond=0)
    if local < evening:
        target = evening
    else:
        target = (local + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
    return target.astimezone(_UTC).replace(tzinfo=None)