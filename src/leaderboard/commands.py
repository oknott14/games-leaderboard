"""Parse chat commands (`@leaderboard weekly maptap`) into queries.

Shared by @mentions, the slash command, `leaderboard show` and the scheduler.
See docs/plan/04-commands-formatting.md.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from leaderboard.boards.config import BoardConfig
    from leaderboard.config import GameConfig

ANCHOR_WORDS: frozenset[str] = frozenset({"today", "yesterday", "lastweek", "lastmonth"})
RESERVED_WORDS: frozenset[str] = frozenset({"help", "games", "boards"})


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
    """`today`, `yesterday`, `lastweek`/`last_week`, `lastmonth`/`last_month` or `YYYY-MM-DD`."""
    raise NotImplementedError  # T-401
