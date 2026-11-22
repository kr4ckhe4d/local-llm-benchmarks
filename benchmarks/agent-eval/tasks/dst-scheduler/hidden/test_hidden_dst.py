from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from cronlite.schedule import next_daily_run, runs_between

SYD, NY = ZoneInfo("Australia/Sydney"), ZoneInfo("America/New_York")


def wall(t, zone):
    t = t.astimezone(zone)
    return (t.year, t.month, t.day, t.hour, t.minute)


def test_sydney_dst_end_next_run():
    now = datetime(2026, 4, 5, 9, 30, tzinfo=SYD)  # DST ends 03:00 that morning
    assert wall(next_daily_run(now, 9, 0, "Australia/Sydney"), SYD) == (2026, 4, 6, 9, 0)


def test_sydney_dst_start_next_run():
    now = datetime(2026, 10, 3, 9, 30, tzinfo=SYD)  # DST starts 02:00 on 4 Oct
    assert wall(next_daily_run(now, 9, 0, "Australia/Sydney"), SYD) == (2026, 10, 4, 9, 0)


def test_new_york_spring_forward_from_utc_now():
    now = datetime(2026, 3, 7, 23, 0, tzinfo=timezone.utc)  # 18:00 EST on 7 Mar
    r = next_daily_run(now, 9, 0, "America/New_York")
    assert wall(r, NY) == (2026, 3, 8, 9, 0)
    assert r.utcoffset().total_seconds() == -4 * 3600


def test_result_is_aware_in_zone():
    r = next_daily_run(datetime(2026, 4, 5, 12, 0, tzinfo=SYD), 9, 0, "Australia/Sydney")
    assert r.tzinfo is not None and r.utcoffset() == r.astimezone(SYD).utcoffset()


def test_runs_between_across_both_sydney_transitions():
    start = datetime(2026, 4, 3, 0, 0, tzinfo=SYD)
    end = datetime(2026, 4, 8, 0, 0, tzinfo=SYD)
    runs = runs_between(start, end, 9, 0, "Australia/Sydney")
    assert [wall(r, SYD) for r in runs] == [(2026, 4, d, 9, 0) for d in range(3, 8)]
    start = datetime(2026, 10, 2, 0, 0, tzinfo=SYD)
    end = datetime(2026, 10, 7, 0, 0, tzinfo=SYD)
    runs = runs_between(start, end, 9, 0, "Australia/Sydney")
    assert [wall(r, SYD) for r in runs] == [(2026, 10, d, 9, 0) for d in range(2, 7)]


def test_runs_between_end_exclusive_and_start_inclusive():
    start = datetime(2026, 3, 6, 9, 0, tzinfo=NY)
    end = datetime(2026, 3, 10, 9, 0, tzinfo=NY)
    runs = runs_between(start, end, 9, 0, "America/New_York")
    assert [wall(r, NY) for r in runs] == [(2026, 3, d, 9, 0) for d in (6, 7, 8, 9)]


def test_long_horizon_never_drifts():
    start = datetime(2026, 1, 1, tzinfo=SYD)
    runs = runs_between(start, datetime(2027, 1, 1, tzinfo=SYD), 9, 0, "Australia/Sydney")
    assert len(runs) == 365
    assert all(r.astimezone(SYD).hour == 9 and r.astimezone(SYD).minute == 0 for r in runs)
