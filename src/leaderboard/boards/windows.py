"""Built-in windows: which results a board covers, relative to its anchor date.

Every range ends at the anchor (inclusive), so "this week" is Monday through the anchor, and
anchoring at last Sunday gives all of last week.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from functools import partial

from pydantic import BaseModel, ConfigDict, Field

from leaderboard.boards.core import DateRange, Entry, WindowResult, chronological_key, group_by_player
from leaderboard.boards.registry import window


class CountParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    n: int = Field(ge=1)


def _shifted(rng: DateRange, days: int) -> DateRange:
    assert rng.start is not None
    return DateRange(rng.start - timedelta(days=days), rng.end - timedelta(days=days))


def _clamped(year: int, month: int, day: int) -> date:
    """`date(year, month, day)`, clamping the day to the month's length (Mar 31 → Feb 28)."""
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))


@window("day", description="The anchor day only")
def day(anchor: date, params: None) -> WindowResult:
    rng = DateRange(anchor, anchor)
    return WindowResult(rng, previous=_shifted(rng, 1))


@window("week", description="Monday through the anchor day")
def week(anchor: date, params: None) -> WindowResult:
    rng = DateRange(anchor - timedelta(days=anchor.weekday()), anchor)
    return WindowResult(rng, previous=_shifted(rng, 7))  # the same weekdays last week


@window("month", description="The 1st of the anchor's month through the anchor day")
def month(anchor: date, params: None) -> WindowResult:
    last_month_end = anchor.replace(day=1) - timedelta(days=1)
    previous = DateRange(last_month_end.replace(day=1), _clamped(last_month_end.year, last_month_end.month, anchor.day))
    return WindowResult(DateRange(anchor.replace(day=1), anchor), previous=previous)


@window("year", description="January 1st through the anchor day")
def year(anchor: date, params: None) -> WindowResult:
    previous = DateRange(date(anchor.year - 1, 1, 1), _clamped(anchor.year - 1, anchor.month, anchor.day))
    return WindowResult(DateRange(anchor.replace(month=1, day=1), anchor), previous=previous)


@window("all", description="All time up to the anchor day")
def all_time(anchor: date, params: None) -> WindowResult:
    return WindowResult(DateRange(None, anchor))


@window("rolling_days", params=CountParams, description="The last n days, ending on the anchor day")
def rolling_days(anchor: date, params: CountParams) -> WindowResult:
    rng = DateRange(anchor - timedelta(days=params.n - 1), anchor)
    return WindowResult(rng, previous=_shifted(rng, params.n))


@window("last_n", params=CountParams, description="Each player's n most recent results up to the anchor day")
def last_n(anchor: date, params: CountParams) -> WindowResult:
    return WindowResult(DateRange(None, anchor), select=partial(_latest_per_player, n=params.n))


def _latest_per_player(entries: list[Entry], n: int) -> list[Entry]:
    """Keep each player's `n` most recent entries, preserving chronological order."""
    kept = {
        id(e)
        for player_entries in group_by_player(entries).values()
        for e in sorted(player_entries, key=chronological_key)[-n:]
    }
    return [e for e in entries if id(e) in kept]
