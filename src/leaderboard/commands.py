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

ANCHOR_WORDS: frozenset[str] = frozenset({"today", "yesterday", "lastweek", "lastmonth"})
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


def parse_command(
    text: str, *, today: date, games: Mapping[str, GameConfig], boards: Mapping[str, BoardConfig]
) -> Query | InfoRequest | CommandError:
    raise NotImplementedError  # T-402, T-403


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
