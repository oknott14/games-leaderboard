from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from leaderboard.crontab import _weekday_names, cron_trigger

NY = ZoneInfo("America/New_York")
THU = datetime(2026, 9, 24, 12, 0, tzinfo=NY)


def next_run(expression: str) -> datetime:
    fire = cron_trigger(expression, NY).get_next_fire_time(None, THU)
    assert fire is not None
    return fire


@pytest.mark.parametrize(
    ("expression", "weekday"),
    [("0 9 * * 1", "Monday"), ("0 9 * * MON", "Monday"), ("0 9 * * 0", "Sunday"), ("0 9 * * 7", "Sunday"),
     ("0 9 * * 5", "Friday"), ("0 9 * * sat", "Saturday")],
)
def test_weekdays_follow_crontab_numbering(expression: str, weekday: str) -> None:
    assert next_run(expression).strftime("%A") == weekday


@pytest.mark.parametrize(
    ("field", "names"),
    [("1-5", "mon,tue,wed,thu,fri"), ("0,6", "sun,sat"), ("*/2", "sun,tue,thu,sat"), ("1-5/2", "mon,wed,fri"),
     ("mon-fri", "mon-fri"), ("*", "*"), ("0-7", "sun,mon,tue,wed,thu,fri,sat")],
)
def test_weekday_translation(field: str, names: str) -> None:
    assert _weekday_names(field) == names


def test_daily_and_timezone() -> None:
    assert next_run("0 9 * * *") == datetime(2026, 9, 25, 9, 0, tzinfo=NY)


@pytest.mark.parametrize(("expression", "match"), [("0 9 * *", "expected 5 fields"), ("0 9 * * 8", "out of range"),
                                                   ("0 9 * * 5-1", "runs backwards"), ("0 25 * * *", None)])
def test_invalid(expression: str, match: str | None) -> None:
    with pytest.raises(ValueError, match=match):
        cron_trigger(expression)
