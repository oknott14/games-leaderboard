"""Runs a board for one game: window → rows → dedupe → values → board type → standings.

The service supplies `load_rows`; the engine never touches the database.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from leaderboard.boards.core import DateRange, ResultRow, Standing

if TYPE_CHECKING:
    from leaderboard.boards.config import BoardConfig
    from leaderboard.config import GameConfig


@dataclass(frozen=True)
class GameBoardResult:
    game: GameConfig
    standings: list[Standing]


@dataclass(frozen=True)
class BoardResult:
    board: BoardConfig
    anchor: date
    range: DateRange
    unit: str | None
    sections: list[GameBoardResult]  # one per applicable game, in games-dict order


def board_applies(board: BoardConfig, game: GameConfig) -> bool:
    raise NotImplementedError  # T-315


def board_range(board: BoardConfig, anchor: date) -> DateRange:
    """The window's date range, for headers."""
    raise NotImplementedError  # T-315


def board_unit(board: BoardConfig) -> str | None:
    """The board type's unit, else the aggregator's."""
    raise NotImplementedError  # T-315


def run_board(
    board: BoardConfig,
    game: GameConfig,
    anchor: date,
    load_rows: Callable[[DateRange], list[ResultRow]],
) -> list[Standing]:
    """All standings for `game` (no truncation; `board.limit` is applied by formatting)."""
    raise NotImplementedError  # T-315
