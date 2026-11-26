"""Hong Kong post times from the playbook: odd days 12:20, even days 21:00."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

HK = ZoneInfo("Asia/Hong_Kong")


def tomorrow_hk(now: datetime | None = None) -> date:
    current = now or datetime.now(HK)
    if current.tzinfo is None:
        current = current.replace(tzinfo=HK)
    return (current.astimezone(HK) + timedelta(days=1)).date()


def post_at(start: date, day: int) -> datetime:
    posted = start + timedelta(days=day - 1)
    hour, minute = (12, 20) if day % 2 == 1 else (21, 0)
    return datetime(posted.year, posted.month, posted.day, hour, minute, tzinfo=HK)
