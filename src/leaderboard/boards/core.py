"""Core types of the leaderboard engine. See docs/plan/03-boards-engine.md.

Everything here is pure data or pure functions: no database, chat or formatting.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING, TypeAlias

from pydantic import BaseModel

if TYPE_CHECKING:
    from leaderboard.boards.config import BoardConfig
    from leaderboard.config import DuplicatePolicy, GameConfig

PlayerKey: TypeAlias = tuple[str, str]  # (platform, user_id)


@dataclass(frozen=True)
class ResultRow:
    """A stored game result, as loaded by the service for the engine."""

    player: PlayerKey
    game: str
    played_on: date
    posted_at: datetime  # naive UTC
    score: float
    rounds: tuple[float, ...]


@dataclass(frozen=True)
class DateRange:
    start: date | None  # None = beginning of time
    end: date  # inclusive


@dataclass(frozen=True)
class Entry:
    """One player's value on one day, after duplicate resolution."""

    player: PlayerKey
    played_on: date
    posted_at: datetime
    value: float


@dataclass(frozen=True)
class Standing:
    player: PlayerKey
    value: float
    entries: int  # results that contributed
    rank: int  # competition ranking (1, 1, 3)
    detail: str | None = None  # extra context, e.g. "+120 vs last week"


@dataclass(frozen=True)
class WindowResult:
    range: DateRange  # rows to load
    select: Callable[[list[Entry]], list[Entry]] | None = None  # optional per-player trim


@dataclass(frozen=True)
class AggContext:
    higher_is_better: bool  # the value's direction
    anchor: date
    params: BaseModel | None


@dataclass
class BoardContext:
    game: GameConfig
    board: BoardConfig
    value_name: str
    higher_is_better: bool  # ranking direction, resolved: board → aggregator → value
    anchor: date
    range: DateRange
    entries: list[Entry]  # deduped, valued, window-selected; sorted by played_on
    params: BaseModel | None  # board type params
    aggregate: Callable[[list[Entry]], float | None]  # the board's aggregator, bound
    fetch: Callable[[DateRange], list[Entry]]  # the same pipeline for another range


def chronological_key(item: Entry | ResultRow) -> tuple[date, datetime]:
    """The one ordering rule for "earlier/later": played date, then post time."""
    return (item.played_on, item.posted_at)


def group_by_player(entries: list[Entry]) -> dict[PlayerKey, list[Entry]]:
    """Entries grouped per player, preserving input order within each group."""
    grouped: dict[PlayerKey, list[Entry]] = defaultdict(list)
    for entry in entries:
        grouped[entry.player].append(entry)
    return grouped


def same_value(a: float, b: float) -> bool:
    """Equality for aggregated floats (sums/averages computed in different orders)."""
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)


def dedupe_daily(rows: list[ResultRow], policy: DuplicatePolicy, higher_is_better: bool) -> list[ResultRow]:
    """Keep one row per (player, played_on) according to the game's duplicate policy.

    `first`/`last` pick by post time; `best` picks the best score in `higher_is_better`'s
    direction (ties go to the earliest post). Returns rows sorted by (played_on, posted_at).
    """
    groups: dict[tuple[PlayerKey, date], list[ResultRow]] = defaultdict(list)
    for row in rows:
        groups[(row.player, row.played_on)].append(row)

    def pick(day_rows: list[ResultRow]) -> ResultRow:
        by_time = sorted(day_rows, key=lambda r: r.posted_at)
        if policy == "first":
            return by_time[0]
        if policy == "last":
            return by_time[-1]
        sign = -1 if higher_is_better else 1
        return min(by_time, key=lambda r: sign * r.score)  # min() keeps the earliest on ties

    return sorted((pick(g) for g in groups.values()), key=chronological_key)


def rank(scored: list[tuple[PlayerKey, float, int, str | None]], higher_is_better: bool) -> list[Standing]:
    """Sort `(player, value, entries, detail)` tuples and assign competition ranks (1, 1, 3).

    Equal values share a rank; ties are listed in player order so output is stable.
    """
    sign = -1 if higher_is_better else 1
    ordered = sorted(scored, key=lambda s: (sign * s[1], s[0]))
    standings: list[Standing] = []
    for position, (player, value, entries, detail) in enumerate(ordered, 1):
        tied = standings and same_value(standings[-1].value, value)
        standings.append(Standing(player, value, entries, standings[-1].rank if tied else position, detail))
    return standings
