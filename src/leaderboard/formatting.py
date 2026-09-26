"""Render board results and help text as chat markup (`*bold*`, `_italic_`, emoji)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    from leaderboard.boards.config import BoardConfig
    from leaderboard.boards.engine import BoardResult
    from leaderboard.commands import CommandError
    from leaderboard.config import GameConfig

NameFor: TypeAlias = Callable[[str, str], str]  # (platform, user_id) → display name


def fmt_value(value: float, unit: str | None = None) -> str:
    raise NotImplementedError  # T-404


def format_board(result: BoardResult, name_for: NameFor) -> str:
    raise NotImplementedError  # T-405


def format_info(topic: str, games: Mapping[str, GameConfig], boards: Mapping[str, BoardConfig]) -> str:
    raise NotImplementedError  # T-406


def format_error(err: CommandError) -> str:
    raise NotImplementedError  # T-406
