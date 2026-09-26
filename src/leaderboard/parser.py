"""Turn message text into game results. See docs/plan/01-parsing.md."""

from __future__ import annotations

import importlib
import logging
import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
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
        return _parse_with_plugin(text, game)
    assert game.detect_re is not None and game.score is not None
    if not game.detect_re.search(text):
        return None

    rounds = _extract_rounds(text, game)
    score = _extract_score(text, game, rounds)
    if score is None:
        log.warning("%s: detected, but no score could be read from %r", game.name, text[:80])
        return None

    if game.rounds is not None and game.rounds.check_sum:
        _check_sum(text, game, score, rounds)

    puzzle = None
    if game.puzzle_re is not None and (match := game.puzzle_re.search(text)) and match["value"]:
        puzzle = match["value"].strip()
    return ParsedResult(game=game.name, score=score, rounds=rounds, puzzle=puzzle)


def load_plugin_parser(game: GameConfig) -> PluginParser:
    """Resolve `game.parser` ("module:function"). The plugins dir must be on sys.path.

    Raises `ValueError` naming the game if it can't be loaded. Imports are cached by sys.modules.
    """
    assert game.parser is not None
    module_name, _, func_name = game.parser.partition(":")
    try:
        func = getattr(importlib.import_module(module_name), func_name)
    except (ImportError, AttributeError) as exc:
        raise ValueError(f"game {game.name!r}: can't load parser {game.parser!r}: {exc}") from exc
    if not callable(func):
        raise ValueError(f"game {game.name!r}: parser {game.parser!r} is not callable")
    return func  # type: ignore[no-any-return]


def _parse_with_plugin(text: str, game: GameConfig) -> ParsedResult | None:
    """Run a plugin parser. A plugin can never break parsing for other games or messages:
    exceptions and malformed results are logged and treated as "not detected"."""
    parser = load_plugin_parser(game)
    try:
        result = parser(text)
    except Exception:
        log.exception("%s: parser %s raised on %r; ignoring", game.name, game.parser, text[:80])
        return None
    if result is None:
        return None
    if not isinstance(result, ParsedResult):
        log.warning("%s: parser %s returned %r, not a ParsedResult; ignoring", game.name, game.parser, result)
        return None
    try:
        score = float(result.score)
        rounds = tuple(float(r) for r in result.rounds)
    except (TypeError, ValueError):
        log.warning("%s: parser %s returned non-numeric score/rounds %r; ignoring", game.name, game.parser, result)
        return None
    if not (math.isfinite(score) and all(math.isfinite(r) for r in rounds)):
        log.warning("%s: parser %s returned a non-finite score/round %r; ignoring", game.name, game.parser, result)
        return None
    puzzle = None if result.puzzle is None else str(result.puzzle)
    return replace(result, game=game.name, score=score, rounds=rounds, puzzle=puzzle)


def _extract_score(text: str, game: GameConfig, rounds: tuple[float, ...]) -> float | None:
    assert game.score is not None
    if game.score.from_rounds is not None:
        return reduce_rounds(game.score.from_rounds, rounds)
    assert game.score_re is not None
    match = game.score_re.search(text)
    return parse_number(match["value"], game.score) if match else None


def _check_sum(text: str, game: GameConfig, score: float, rounds: tuple[float, ...]) -> None:
    """Warn when the rounds don't add up to the posted score, including when none were found."""
    if not rounds:
        log.warning("%s: check_sum: no rounds found (layout changed or tiles unmatched?) in %r",
                    game.name, text[:80])
    elif not math.isclose(sum(rounds), score, rel_tol=1e-9, abs_tol=1e-9):
        log.warning(
            "%s: rounds %s add up to %s, not the posted score %s (unmapped or mis-mapped round?) in %r",
            game.name, list(rounds), sum(rounds), score, text[:80],
        )


def _extract_rounds(text: str, game: GameConfig) -> tuple[float, ...]:
    """Find the rounds block, then every item inside it (and only inside it)."""
    if game.rounds is None:
        return ()
    assert game.block_re is not None and game.item_re is not None
    block = game.block_re.search(text)
    if not block or block["block"] is None:
        return ()
    rounds = []
    for item in game.item_re.findall(block["block"]):  # the single group, or the whole match
        value = parse_number(item, game.rounds)
        if value is None:
            log.warning("%s: skipping round %r (not a number and not in rounds.map)", game.name, item)
            continue
        rounds.append(value)
    return tuple(rounds)
