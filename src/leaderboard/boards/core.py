"""Core types of the leaderboard engine. See docs/plan/03-boards-engine.md.

Everything here is pure data or pure functions: no database, chat or formatting.
"""

from __future__ import annotations

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


def dedupe_daily(rows: list[ResultRow], policy: DuplicatePolicy, higher_is_better: bool) -> list[ResultRow]:
    """Keep one row per (player, played_on) according to the game's duplicate policy."""
    raise NotImplementedError  # T-311


def rank(scored: list[tuple[PlayerKey, float, int, str | None]], higher_is_better: bool) -> list[Standing]:
    """Sort `(player, value, entries, detail)` tuples and assign competition ranks."""
    raise NotImplementedError  # T-311
