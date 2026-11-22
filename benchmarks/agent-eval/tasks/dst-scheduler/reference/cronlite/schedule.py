"""Daily schedules in a named time zone."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def _at(day, hour, minute, zone):
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=zone)


def next_daily_run(now: datetime, hour: int, minute: int, tz: str) -> datetime:
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    zone = ZoneInfo(tz)
    local = now.astimezone(zone)
    candidate = _at(local.date(), hour, minute, zone)
    if candidate < now:
        candidate = _at(local.date() + timedelta(days=1), hour, minute, zone)
    return candidate


def runs_between(start: datetime, end: datetime, hour: int, minute: int, tz: str) -> list[datetime]:
    zone = ZoneInfo(tz)
    out = []
    t = next_daily_run(start, hour, minute, tz)
    while t < end:
        out.append(t)
        t = _at(t.date() + timedelta(days=1), hour, minute, zone)
    return out
