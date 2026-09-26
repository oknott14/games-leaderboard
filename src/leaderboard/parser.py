"""Turn message text into game results. See docs/plan/01-parsing.md."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeAlias

from leaderboard.config import parse_number, reduce_rounds

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

    rounds = _extract_rounds(text, game)
    score = _extract_score(text, game, rounds)
    if score is None:
        log.warning("%s: detected, but no score could be read from %r", game.name, text[:80])
        return None

    if game.rounds is not None and game.rounds.check_sum and rounds and sum(rounds) != score:
        log.warning(
            "%s: rounds %s add up to %s, not the posted score %s (unmapped or mis-mapped round?) in %r",
            game.name, list(rounds), sum(rounds), score, text[:80],
        )

    puzzle = None
    if game.puzzle_re is not None and (match := game.puzzle_re.search(text)):
        puzzle = match["value"].strip()
    return ParsedResult(game=game.name, score=score, rounds=rounds, puzzle=puzzle)


def _extract_score(text: str, game: GameConfig, rounds: tuple[float, ...]) -> float | None:
    assert game.score is not None
    if game.score.from_rounds is not None:
        return reduce_rounds(game.score.from_rounds, rounds)
    assert game.score_re is not None
    match = game.score_re.search(text)
    return parse_number(match["value"], game.score) if match else None


def _extract_rounds(text: str, game: GameConfig) -> tuple[float, ...]:
    """Find the rounds block, then every item inside it (and only inside it)."""
    if game.rounds is None or game.block_re is None or game.item_re is None:
        return ()
    block = game.block_re.search(text)
    if not block:
        return ()
    rounds = []
    for item in game.item_re.findall(block["block"]):  # the single group, or the whole match
        value = parse_number(item, game.rounds)
        if value is None:
            log.warning("%s: skipping round %r (not a number and not in rounds.map)", game.name, item)
            continue
        rounds.append(value)
    return tuple(rounds)
