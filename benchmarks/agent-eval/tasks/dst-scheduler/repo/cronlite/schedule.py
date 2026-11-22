"""Daily schedules in a named time zone."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


def next_daily_run(now: datetime, hour: int, minute: int, tz: str) -> datetime:
    """Next time at or after `now` (aware) when it is hour:minute in zone `tz`."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    zone = ZoneInfo(tz)
    local = now.astimezone(zone)
    candidate = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate < local:
        candidate = _plus_one_day(candidate, zone)
    return candidate


def _plus_one_day(t: datetime, zone: ZoneInfo) -> datetime:
    return (t.astimezone(timezone.utc) + timedelta(days=1)).astimezone(zone)


def runs_between(start: datetime, end: datetime, hour: int, minute: int, tz: str) -> list[datetime]:
    zone = ZoneInfo(tz)
    out = []
    t = next_daily_run(start, hour, minute, tz)
    while t < end:
        out.append(t)
        t = _plus_one_day(t, zone)
    return out
