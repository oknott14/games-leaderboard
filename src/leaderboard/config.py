"""Game config schema: one YAML file per game in `games/`.

A game config says how to recognise a game's share text and which numbers a post yields.
See docs/plan/01-parsing.md for the extraction rules.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Flag = Literal["IGNORECASE", "DOTALL", "MULTILINE"]
Reducer = Literal["sum", "avg", "max", "min"]
DuplicatePolicy = Literal["first", "best", "last"]

SLUG = r"^[a-z0-9_]+$"


class NumberSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["int", "float"] = "int"
    map: dict[str, float] = {}  # raw capture → value, applied before conversion


class ScoreSpec(NumberSpec):
    pattern: str | None = None  # must contain (?P<value>…)
    from_rounds: Reducer | None = None  # exactly one of pattern / from_rounds


class RoundsSpec(NumberSpec):
    block: str  # must contain (?P<block>…)
    item: str  # findall inside the block; the single group, or the whole match
    check_sum: bool = False  # warn if sum(rounds) != posted score (needs score.pattern)


class PuzzleSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pattern: str  # must contain (?P<value>…)


class ValueSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_rounds: Reducer
    higher_is_better: bool | None = None  # None → the game's default


class GameConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=SLUG)  # defaults to the file stem (load_games)
    display_name: str | None = None
    aliases: list[str] = []
    enabled: bool = True
    flags: list[Flag] = []
    detect: str | None = None  # required unless `parser` is set
    score: ScoreSpec | None = None  # required unless `parser` is set
    rounds: RoundsSpec | None = None
    puzzle: PuzzleSpec | None = None
    parser: str | None = None  # "module:function" plugin parser (see parser.PluginParser)
    higher_is_better: bool = True
    duplicates: DuplicatePolicy = "first"
    values: dict[str, ValueSpec] = {}  # extra values; "score" is implicit and reserved

    @property
    def label(self) -> str:
        """`display_name`, or `name` when unset."""
        raise NotImplementedError  # T-105

    def value_names(self) -> list[str]:
        """`["score", *values]`."""
        raise NotImplementedError  # T-105

    def value(self, name: str, score: float, rounds: tuple[float, ...]) -> float | None:
        """Compute a named value from a result; `None` if it can't be computed."""
        raise NotImplementedError  # T-105

    def higher_is_better_for(self, value_name: str) -> bool:
        raise NotImplementedError  # T-105


def load_games(directory: Path) -> dict[str, GameConfig]:
    """Load, validate and return the enabled games in `directory`, keyed by name."""
    raise NotImplementedError  # T-102
