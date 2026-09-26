"""Game config schema: one YAML file per game in `games/`.

A game config says how to recognise a game's share text and which numbers a post yields.
See docs/plan/01-parsing.md for the extraction rules.
"""

from __future__ import annotations

import re
from functools import cached_property
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Flag = Literal["IGNORECASE", "DOTALL", "MULTILINE"]
Reducer = Literal["sum", "avg", "max", "min"]
DuplicatePolicy = Literal["first", "best", "last"]

SLUG = r"^[a-z0-9_]+$"
_SLUG = re.compile(SLUG)
_PLUGIN_REF = re.compile(r"^[A-Za-z_][\w.]*:[A-Za-z_]\w*$")  # module.path:function


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

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.parser is not None:
            if not _PLUGIN_REF.match(self.parser):
                raise ValueError(f"parser: expected 'module:function', got {self.parser!r}")
            regex_fields = [f for f in ("detect", "score", "rounds", "puzzle") if getattr(self, f) is not None]
            if regex_fields:
                raise ValueError(f"parser: can't be combined with {', '.join(regex_fields)}")
        else:
            if self.detect is None or self.score is None:
                raise ValueError("a game needs either `parser`, or both `detect` and `score`")
            self._check_patterns()

        for name, spec in self.values.items():
            if name == "score":
                raise ValueError("values: 'score' is reserved (it is always available)")
            if not _SLUG.match(name):
                raise ValueError(f"values: name {name!r} must match {SLUG}")
            if self.rounds is None and self.parser is None:
                raise ValueError(f"values.{name}.from_rounds: requires a `rounds` section")
        return self

    def _check_patterns(self) -> None:
        assert self.detect is not None and self.score is not None
        self._compile("detect", self.detect)

        if (self.score.pattern is None) == (self.score.from_rounds is None):
            raise ValueError("score: set exactly one of `pattern` or `from_rounds`")
        if self.score.pattern is not None:
            self._require_group("score.pattern", self.score.pattern, "value")
        elif self.rounds is None:
            raise ValueError("score.from_rounds: requires a `rounds` section")

        if self.puzzle is not None:
            self._require_group("puzzle.pattern", self.puzzle.pattern, "value")

        if self.rounds is not None:
            self._require_group("rounds.block", self.rounds.block, "block")
            if self._compile("rounds.item", self.rounds.item).groups > 1:
                raise ValueError("rounds.item: use at most one capturing group (or (?:…) for grouping)")
            if self.rounds.check_sum and self.score.pattern is None:
                raise ValueError("rounds.check_sum: needs `score.pattern` (a from_rounds score always matches)")

    def _compile(self, field: str, pattern: str) -> re.Pattern[str]:
        try:
            return re.compile(pattern, self.re_flags)
        except re.error as exc:
            raise ValueError(f"{field}: invalid regex: {exc}") from None

    def _require_group(self, field: str, pattern: str, group: str) -> None:
        if group not in self._compile(field, pattern).groupindex:
            raise ValueError(f"{field}: must contain a named group (?P<{group}>…)")

    @property
    def re_flags(self) -> re.RegexFlag:
        flags = re.RegexFlag(0)
        for name in self.flags:
            flags |= re.RegexFlag[name]
        return flags

    # Compiled patterns, for the parser. Validation guarantees they compile.

    @cached_property
    def detect_re(self) -> re.Pattern[str] | None:
        return re.compile(self.detect, self.re_flags) if self.detect is not None else None

    @cached_property
    def score_re(self) -> re.Pattern[str] | None:
        pattern = self.score.pattern if self.score is not None else None
        return re.compile(pattern, self.re_flags) if pattern is not None else None

    @cached_property
    def puzzle_re(self) -> re.Pattern[str] | None:
        return re.compile(self.puzzle.pattern, self.re_flags) if self.puzzle is not None else None

    @cached_property
    def block_re(self) -> re.Pattern[str] | None:
        return re.compile(self.rounds.block, self.re_flags) if self.rounds is not None else None

    @cached_property
    def item_re(self) -> re.Pattern[str] | None:
        return re.compile(self.rounds.item, self.re_flags) if self.rounds is not None else None

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


def parse_number(raw: str, spec: NumberSpec) -> float | None:
    """Convert a captured string to a number: apply `spec.map`, strip separators, convert.

    Returns `None` when the value can't be parsed.
    """
    raw = raw.strip()
    if raw in spec.map:
        return float(spec.map[raw])
    cleaned = re.sub(r"[,_\s]", "", raw)
    try:
        return float(int(cleaned)) if spec.type == "int" else float(cleaned)
    except ValueError:
        return None


def load_games(directory: Path) -> dict[str, GameConfig]:
    """Load, validate and return the enabled games in `directory`, keyed by name."""
    raise NotImplementedError  # T-102
