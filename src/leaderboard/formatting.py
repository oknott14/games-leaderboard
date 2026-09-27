"""Render board results and help text as chat markup (`*bold*`, `_italic_`, emoji)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, TypeAlias

from leaderboard.boards.core import DateRange, Standing

from leaderboard.boards.config import POSITIONAL

if TYPE_CHECKING:
    from leaderboard.boards.config import BoardConfig, ComponentRef
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


MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}
NO_RESULTS = "_No results yet._"


def format_board(result: BoardResult, name_for: NameFor) -> str:
    """A header, then one section per game with its top `board.limit` standings.

        *Weekly total* — Sep 15–21
        *MapTap*
        🥇 Alice — 4,321 · 5 games
        🥈 Bob — 4,100 · 5 games
    """
    header = f"*{result.board.title or result.board.name}* — {fmt_range(result.range)}"
    if not result.sections:
        return f"{header}\n{NO_RESULTS}"
    sections = []
    for section in result.sections:
        lines = [f"*{section.game.label}*"]
        for standing in section.standings[: result.board.limit]:
            lines.append(_standing_line(standing, result.unit, name_for))
        sections.append("\n".join(lines))
    return header + "\n" + "\n\n".join(sections)


def _standing_line(standing: Standing, unit: str | None, name_for: NameFor) -> str:
    place = MEDALS.get(standing.rank, f"{standing.rank}.")
    line = f"{place} {name_for(*standing.player)} — {fmt_value(standing.value, unit)}"
    if standing.detail:
        line += f" · {standing.detail}"
    elif standing.entries > 1 and unit != "games":
        line += f" · {standing.entries} games"
    return line


HELP = """*Leaderboard commands* (words can go in any order)
• `today` · `yesterday` · `2026-09-20`: daily results
• `weekly` · `weekly lastweek` · `average lastmonth`: any saved board (see `boards`)
• `weekly maptap tg`: only some games (see `games`)
• `maptap avg month`: build a board on the fly from a value, aggregator and window
• `krillion best_round best all`: the all-time best single round
• `tg median last_n=10`: parameters as `name=value`
• `games` · `boards` · `help`"""


def format_info(topic: str, games: Mapping[str, GameConfig], boards: Mapping[str, BoardConfig]) -> str:
    if topic == "games":
        return _format_games(games)
    if topic == "boards":
        return _format_boards(boards)
    return HELP


def format_error(err: CommandError) -> str:
    text = err.message
    if err.suggestions:
        text += "\nDid you mean: " + ", ".join(f"`{s}`" for s in err.suggestions) + "?"
    return text + "\nTry `help`."


def _format_games(games: Mapping[str, GameConfig]) -> str:
    if not games:
        return "*Games*\n_No games configured._"
    lines = ["*Games*"]
    for game in games.values():
        names = ", ".join(f"`{n}`" for n in (game.name, *game.aliases))
        lines.append(f"• *{game.label}* ({names}): values {', '.join(f'`{v}`' for v in game.value_names())}")
    return "\n".join(lines)


def _format_boards(boards: Mapping[str, BoardConfig]) -> str:
    from leaderboard.boards.registry import AGGREGATORS, BOARD_TYPES, WINDOWS  # filled at startup

    lines = ["*Saved boards*"]
    lines += [f"• `{name}`: {board.title or name} ({_composition(board)})" for name, board in boards.items()]
    if not boards:
        lines.append("_None; build one on the fly, e.g._ `maptap avg month`")
    for heading, table in (("Aggregators", AGGREGATORS), ("Windows", WINDOWS), ("Board types", BOARD_TYPES)):
        lines.append(f"\n*{heading}*")
        for name, reg in table.items():
            fields = f" ({', '.join(reg.params.model_fields)})" if reg.params else ""
            lines.append(f"• `{name}`{fields}: {reg.description}" if reg.description else f"• `{name}`{fields}")
    return "\n".join(lines)


def _composition(board: BoardConfig) -> str:
    """`week · sum · score`, `last_n 5 · avg · score`, `daily_wins · month · score`."""
    def ref(component: ComponentRef) -> str:
        params = " ".join(str(v) if k == POSITIONAL else f"{k}={v}" for k, v in component.params.items())
        return f"{component.name} {params}" if params else component.name

    parts = [ref(board.window), ref(board.aggregate), board.value]
    if board.type.name != "ranked":
        parts = [ref(board.type), ref(board.window), board.value]
    return " · ".join(parts)
