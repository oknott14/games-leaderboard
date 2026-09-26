"""Built-in windows: which results a board covers, relative to its anchor date.

Every range ends at the anchor (inclusive), so "this week" is Monday through the anchor, and
anchoring at last Sunday gives all of last week.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from functools import partial

from pydantic import BaseModel, ConfigDict, Field

from leaderboard.boards.core import DateRange, Entry, PlayerKey, WindowResult
from leaderboard.boards.registry import window


class CountParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    n: int = Field(ge=1)


@window("day", description="The anchor day only")
def day(anchor: date, params: None) -> WindowResult:
    return WindowResult(DateRange(anchor, anchor))


@window("week", description="Monday through the anchor day")
def week(anchor: date, params: None) -> WindowResult:
    return WindowResult(DateRange(anchor - timedelta(days=anchor.weekday()), anchor))


@window("month", description="The 1st of the anchor's month through the anchor day")
def month(anchor: date, params: None) -> WindowResult:
    return WindowResult(DateRange(anchor.replace(day=1), anchor))


@window("year", description="January 1st through the anchor day")
def year(anchor: date, params: None) -> WindowResult:
    return WindowResult(DateRange(anchor.replace(month=1, day=1), anchor))


@window("all", description="All time up to the anchor day")
def all_time(anchor: date, params: None) -> WindowResult:
    return WindowResult(DateRange(None, anchor))


@window("rolling_days", params=CountParams, description="The last n days, ending on the anchor day")
def rolling_days(anchor: date, params: CountParams) -> WindowResult:
    return WindowResult(DateRange(anchor - timedelta(days=params.n - 1), anchor))


@window("last_n", params=CountParams, description="Each player's n most recent results up to the anchor day")
def last_n(anchor: date, params: CountParams) -> WindowResult:
    return WindowResult(DateRange(None, anchor), select=partial(_latest_per_player, n=params.n))


def _latest_per_player(entries: list[Entry], n: int) -> list[Entry]:
    """Keep each player's `n` most recent entries, preserving chronological order."""
    by_player: dict[PlayerKey, list[Entry]] = defaultdict(list)
    for entry in entries:
        by_player[entry.player].append(entry)
    kept = {
        id(e)
        for player_entries in by_player.values()
        for e in sorted(player_entries, key=lambda e: (e.played_on, e.posted_at))[-n:]
    }
    return [e for e in entries if id(e) in kept]
