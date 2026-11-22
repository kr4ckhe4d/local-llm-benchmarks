from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from cronlite.schedule import next_daily_run, runs_between

SYD = ZoneInfo("Australia/Sydney")


def test_same_day_when_time_ahead():
    now = datetime(2026, 6, 10, 7, 0, tzinfo=SYD)
    assert next_daily_run(now, 9, 0, "Australia/Sydney") == datetime(2026, 6, 10, 9, 0, tzinfo=SYD)


def test_next_day_when_passed():
    now = datetime(2026, 6, 10, 9, 30, tzinfo=SYD)
    assert next_daily_run(now, 9, 0, "Australia/Sydney") == datetime(2026, 6, 11, 9, 0, tzinfo=SYD)


def test_exactly_now_is_now():
    now = datetime(2026, 6, 10, 9, 0, tzinfo=SYD)
    assert next_daily_run(now, 9, 0, "Australia/Sydney") == now


def test_naive_rejected():
    with pytest.raises(ValueError):
        next_daily_run(datetime(2026, 6, 10, 9, 0), 9, 0, "UTC")


def test_runs_between_winter():
    start = datetime(2026, 6, 1, 0, 0, tzinfo=SYD)
    end = datetime(2026, 6, 4, 0, 0, tzinfo=SYD)
    assert [r.day for r in runs_between(start, end, 9, 0, "Australia/Sydney")] == [1, 2, 3]
