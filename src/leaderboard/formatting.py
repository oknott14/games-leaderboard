"""Render board results and help text as chat markup (`*bold*`, `_italic_`, emoji)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, TypeAlias

from leaderboard.boards.core import DateRange

if TYPE_CHECKING:
    from leaderboard.boards.config import BoardConfig
    from leaderboard.boards.engine import BoardResult
    from leaderboard.commands import CommandError
    from leaderboard.config import GameConfig

NameFor: TypeAlias = Callable[[str, str], str]  # (platform, user_id) → display name


def fmt_value(value: float, unit: str | None = None) -> str:
    """`38532` → `38,532`, `4.25` → `4.3`, unit `±` → `+120`, other units appended (`5 days`)."""
    number = Decimal(str(value))
    whole = number == number.to_integral_value()
    rounded = number if whole else number.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    text = f"{rounded:{'+' if unit == '±' else ''},{'.0f' if whole else '.1f'}}"
    if unit and unit != "±":
        singular = unit[:-1] if unit.endswith("s") and number == 1 else unit
        text += f" {singular}"
    return text


def fmt_range(date_range: DateRange) -> str:
    """`Tue Sep 23`, `Sep 15–21`, `Aug 28 – Sep 3`, `Dec 28, 2025 – Jan 3, 2026`, `all time to Sep 24`."""
    start, end = date_range.start, date_range.end
    if start is None:
        return f"all time to {_md(end)}"
    if start == end:
        return f"{end:%a} {_md(end)}"
    if start.year != end.year:
        return f"{_md(start)}, {start.year} – {_md(end)}, {end.year}"
    if start.month != end.month:
        return f"{_md(start)} – {_md(end)}"
    return f"{_md(start)}–{end.day}"


def _md(day: date) -> str:
    return f"{day:%b} {day.day}"


def format_board(result: BoardResult, name_for: NameFor) -> str:
    raise NotImplementedError  # T-405


def format_info(topic: str, games: Mapping[str, GameConfig], boards: Mapping[str, BoardConfig]) -> str:
    raise NotImplementedError  # T-406


def format_error(err: CommandError) -> str:
    raise NotImplementedError  # T-406
