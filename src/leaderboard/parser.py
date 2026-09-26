"""Turn message text into game results. See docs/plan/01-parsing.md."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeAlias

from leaderboard.config import parse_number

if TYPE_CHECKING:
    from leaderboard.config import GameConfig

log = logging.getLogger(__name__)


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
    results = []
    for game in games:
        result = _parse_game(text, game)
        if result is not None:
            results.append(result)
    return results


def _parse_game(text: str, game: GameConfig) -> ParsedResult | None:
    if game.parser is not None:
        return None  # plugin parsers: T-106
    assert game.detect_re is not None and game.score is not None
    if not game.detect_re.search(text):
        return None

    score = _extract_score(text, game)
    if score is None:
        log.warning("%s: detected, but no score could be read from %r", game.name, text[:80])
        return None

    puzzle = None
    if game.puzzle_re is not None and (match := game.puzzle_re.search(text)):
        puzzle = match["value"].strip()
    return ParsedResult(game=game.name, score=score, puzzle=puzzle)


def _extract_score(text: str, game: GameConfig) -> float | None:
    assert game.score is not None
    if game.score_re is None:
        return None  # score.from_rounds: T-104
    match = game.score_re.search(text)
    return parse_number(match["value"], game.score) if match else None
