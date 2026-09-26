from __future__ import annotations

import re
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from leaderboard.config import GameConfig
from leaderboard.parser import ParsedResult

PARSING_DOC = Path(__file__).parents[1] / "docs" / "plan" / "01-parsing.md"


def minimal(name: str = "g") -> GameConfig:
    """The smallest valid game (detect + score pattern)."""
    return GameConfig(name=name, detect="x", score={"pattern": "(?P<value>\\d+)"})


def doc_game_examples() -> dict[str, str]:
    """The `# games/<name>.yaml` example blocks from 01-parsing.md, keyed by game name."""
    blocks = re.findall(r"```yaml\n(# games/(\w+)\.yaml.*?)```", PARSING_DOC.read_text(), re.S)
    return {name: body for body, name in blocks}


def test_doc_has_all_three_examples() -> None:
    assert set(doc_game_examples()) == {"maptap", "timeguessr", "krillion"}


@pytest.mark.parametrize("name", sorted(doc_game_examples()))
def test_doc_examples_validate(name: str) -> None:
    game = GameConfig.model_validate(yaml.safe_load(doc_game_examples()[name]) | {"name": name})
    assert game.name == name
    assert game.score is not None and game.score.pattern


def test_krillion_example_keeps_emoji_map_and_check_sum() -> None:
    raw = yaml.safe_load(doc_game_examples()["krillion"]) | {"name": "krillion"}
    game = GameConfig.model_validate(raw)
    assert game.rounds is not None and game.rounds.check_sum
    assert game.rounds.map["🌟"] == 100 and game.rounds.map[":izakaya_lantern:"] == 85


def test_defaults() -> None:
    game = minimal()
    assert (game.enabled, game.higher_is_better, game.duplicates) == (True, True, "first")
    assert (game.aliases, game.flags, game.values) == ([], [], {})


def test_mutable_defaults_not_shared() -> None:
    a, b = minimal("a"), minimal("b")
    a.aliases.append("x")
    assert b.aliases == []


@pytest.mark.parametrize(
    "raw",
    [
        {"name": "g", "detect": "x", "sneaky": 1},  # unknown top-level key
        {"name": "g", "score": {"pattern": "(?P<value>1)", "patern": "typo"}},  # nested
        {"name": "g", "rounds": {"block": "b", "item": "i", "extra": True}},
        {"name": "g", "values": {"best": {"from_rounds": "max", "x": 1}}},
    ],
)
def test_unknown_keys_rejected(raw: dict) -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        GameConfig.model_validate(raw)


@pytest.mark.parametrize("name", ["MapTap", "map-tap", "map tap", ""])
def test_name_must_be_slug(name: str) -> None:
    with pytest.raises(ValidationError, match="should match pattern"):
        minimal(name)


@pytest.mark.parametrize(
    "raw",
    [
        {"name": "g", "flags": ["VERBOSE"]},
        {"name": "g", "duplicates": "worst"},
        {"name": "g", "values": {"v": {"from_rounds": "median"}}},
        {"name": "g", "score": {"type": "decimal"}},
    ],
)
def test_literal_fields_rejected(raw: dict) -> None:
    with pytest.raises(ValidationError):
        GameConfig.model_validate(raw)


def test_parsed_result_is_frozen_with_defaults() -> None:
    result = ParsedResult(game="krillion", score=505.0)
    assert (result.rounds, result.puzzle) == ((), None)
    with pytest.raises(FrozenInstanceError):
        result.score = 1.0  # type: ignore[misc]
