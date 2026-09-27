"""Parse chat commands (`@leaderboard weekly maptap`) into queries.

Shared by @mentions, the slash command, `leaderboard show` and the scheduler.
See docs/plan/04-commands-formatting.md.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from leaderboard.boards.config import BoardConfig
    from leaderboard.config import GameConfig

ANCHOR_WORDS: frozenset[str] = frozenset({"today", "yesterday", "lastweek", "last_week", "lastmonth", "last_month"})
RESERVED_WORDS: frozenset[str] = frozenset({"help", "games", "boards"})

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class Query:
    board: BoardConfig  # saved or ad hoc
    games: list[str] | None  # None = all applicable
    anchor: date


@dataclass(frozen=True)
class InfoRequest:
    topic: Literal["help", "games", "boards"]


@dataclass(frozen=True)
class CommandError:
    message: str
    suggestions: list[str] = field(default_factory=list)


SHORTCUT_BOARDS = {"lastweek": "weekly", "last_week": "weekly", "lastmonth": "average", "last_month": "average"}
DEFAULT_SHORTCUT = "daily"


def parse_command(
    text: str, *, today: date, games: Mapping[str, GameConfig], boards: Mapping[str, BoardConfig]
) -> Query | InfoRequest | CommandError:
    """Parse the words after `@leaderboard` / `/leaderboard`. Words may come in any order."""
    tokens = text.lower().split()
    if not tokens:
        return InfoRequest("help")
    if tokens[0] in RESERVED_WORDS:
        if len(tokens) > 1:
            return CommandError(f"`{tokens[0]}` doesn't take anything else")
        return InfoRequest(tokens[0])  # type: ignore[arg-type]

    game_tokens = _game_tokens(games)
    board: BoardConfig | None = None
    anchor: date | None = None
    anchor_token: str | None = None
    selected: list[str] = []

    for token in tokens:
        if token in RESERVED_WORDS:
            return CommandError(f"`{token}` has to be on its own")
        if (resolved := resolve_anchor(token, today)) is not None:
            if anchor is not None:
                return CommandError(f"Two dates: `{anchor_token}` and `{token}`; pick one")
            anchor, anchor_token = resolved, token
        elif token in boards:
            if board is not None:
                return CommandError(f"Two boards: `{board.name}` and `{token}`; pick one")
            board = boards[token]
        elif token in game_tokens:
            if game_tokens[token] not in selected:
                selected.append(game_tokens[token])
        else:
            return CommandError(f"I didn't understand `{token}`")

    if board is None:
        shortcut = SHORTCUT_BOARDS.get(anchor_token or "", DEFAULT_SHORTCUT)
        if shortcut not in boards:
            return CommandError(f"There's no `{shortcut}` board in boards.yaml")
        board = boards[shortcut]
    return Query(board, selected or None, anchor or today)


def _game_tokens(games: Mapping[str, GameConfig]) -> dict[str, str]:
    """Every word that names a game (id, alias, one-word display name) → the game's id."""
    tokens: dict[str, str] = {}
    for game in games.values():
        for token in (game.name, *game.aliases, game.display_name or ""):
            if token:
                tokens[token.lower()] = game.name
    return tokens


def resolve_anchor(token: str, today: date) -> date | None:
    """Resolve an anchor word or `YYYY-MM-DD` to a date; `None` if `token` isn't an anchor.

    Windows end at the anchor, so "last week" is the previous Sunday (the `week` window then
    covers that whole Mon–Sun week) and "last month" is the previous month's last day.
    Accepts both `lastweek` (typed in chat) and `last_week` (boards.yaml schedule anchors).
    """
    match token.lower():
        case "today":
            return today
        case "yesterday":
            return today - timedelta(days=1)
        case "lastweek" | "last_week":
            return today - timedelta(days=today.weekday() + 1)
        case "lastmonth" | "last_month":
            return today.replace(day=1) - timedelta(days=1)
    try:
        return date.fromisoformat(token) if _ISO_DATE.match(token) else None
    except ValueError:
        return None
