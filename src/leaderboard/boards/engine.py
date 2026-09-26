"""Runs a board for one game: window → rows → dedupe → values → board type → standings.

The service supplies `load_rows`; the engine never touches the database.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from leaderboard.boards.core import (
    AggContext,
    BoardContext,
    DateRange,
    Entry,
    ResultRow,
    Standing,
    dedupe_daily,
)
from leaderboard.boards.registry import AGGREGATORS, BOARD_TYPES, WINDOWS, Registered, validate_params

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
    """A board applies to every game that has its value (optionally limited by `board.games`)."""
    if board.games is not None and game.name not in board.games:
        return False
    return board.value in game.value_names()


def board_range(board: BoardConfig, anchor: date) -> DateRange:
    """The window's date range, for headers."""
    win = _lookup(WINDOWS, "window", board.window.name)
    return win.fn(anchor, validate_params(win, board.window.params)).range


def board_unit(board: BoardConfig) -> str | None:
    """The board type's unit, else the aggregator's."""
    btype = _lookup(BOARD_TYPES, "board type", board.type.name)
    return btype.unit or _lookup(AGGREGATORS, "aggregator", board.aggregate.name).unit


def run_board(
    board: BoardConfig,
    game: GameConfig,
    anchor: date,
    load_rows: Callable[[DateRange], list[ResultRow]],
) -> list[Standing]:
    """All standings for `game` (no truncation; `board.limit` is applied by formatting).

    Pipeline: window → load rows → one post per player per day (the game's duplicate policy,
    judged on the score) → the board's value per post → window selection → board type.
    """
    win = _lookup(WINDOWS, "window", board.window.name)
    agg = _lookup(AGGREGATORS, "aggregator", board.aggregate.name)
    btype = _lookup(BOARD_TYPES, "board type", board.type.name)
    window = win.fn(anchor, validate_params(win, board.window.params))
    agg_params = validate_params(agg, board.aggregate.params)
    type_params = validate_params(btype, board.type.params)

    value_higher = game.higher_is_better_for(board.value)
    rank_higher = next(d for d in (board.higher_is_better, agg.higher_is_better, value_higher) if d is not None)
    score_higher = game.higher_is_better_for("score")

    def entries_for(date_range: DateRange) -> list[Entry]:
        rows = dedupe_daily(load_rows(date_range), game.duplicates, score_higher)
        entries = [  # dedupe_daily returns rows chronologically, so entries are too
            Entry(row.player, row.played_on, row.posted_at, value)
            for row in rows
            if (value := game.value(board.value, row.score, row.rounds)) is not None
        ]
        return window.select(entries) if window.select else entries

    board_anchor = anchor

    def aggregate(entries: list[Entry], anchor: date | None = None) -> float | None:
        """The board's aggregator; `anchor` overrides the board's for another period."""
        return agg.fn(entries, AggContext(value_higher, anchor or board_anchor, agg_params))

    ctx = BoardContext(
        game=game,
        board=board,
        value_name=board.value,
        higher_is_better=rank_higher,
        anchor=anchor,
        range=window.range,
        entries=entries_for(window.range),
        params=type_params,
        aggregate=aggregate,
        fetch=entries_for,
        previous=window.previous,
    )
    return btype.fn(ctx)


def _lookup(table: dict[str, Registered], kind: str, name: str) -> Registered:
    try:
        return table[name]
    except KeyError:
        raise ValueError(f"unknown {kind} {name!r}") from None
