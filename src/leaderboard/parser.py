"""Turn message text into game results. See docs/plan/01-parsing.md."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    from leaderboard.config import GameConfig


@dataclass(frozen=True)
class ParsedResult:
    game: str
    score: float
    rounds: tuple[float, ...] = ()
    puzzle: str | None = None


# Signature of a plugin parser named by `GameConfig.parser`. The framework sets `game` on the
# returned value (dataclasses.replace), so plugins may pass any placeholder.
PluginParser: TypeAlias = Callable[[str], ParsedResult | None]


def parse_message(text: str, games: Iterable[GameConfig]) -> list[ParsedResult]:
    """Return a result for every game detected in `text`, in `games` order."""
    raise NotImplementedError  # T-103
