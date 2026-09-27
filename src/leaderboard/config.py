"""Game config schema: one YAML file per game in `games/`.

A game config says how to recognise a game's share text and which numbers a post yields.
See docs/plan/01-parsing.md for the extraction rules.
"""

from __future__ import annotations

import re
import math
from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

Flag = Literal["IGNORECASE", "DOTALL", "MULTILINE"]
Reducer = Literal["sum", "avg", "max", "min"]
DuplicatePolicy = Literal["first", "best", "last"]

SLUG = r"^[a-z0-9_]+$"
_SLUG = re.compile(SLUG)
_PLUGIN_REF = re.compile(r"^[A-Za-z_][\w.]*:[A-Za-z_]\w*$")  # module.path:function


@lru_cache(maxsize=512)
def _compiled(pattern: str, flags: re.RegexFlag) -> re.Pattern[str]:
    return re.compile(pattern, flags)


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

        for name in self.values:
            if name == "score":
                raise ValueError("values: 'score' is reserved (it is always available)")
            if not _SLUG.match(name):
                raise ValueError(f"values: name {name!r} must match {SLUG}")
        if self.values and self.rounds is None and self.parser is None:
            first = next(iter(self.values))
            raise ValueError(f"values.{first}.from_rounds: requires a `rounds` section")
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
            return _compiled(pattern, self.re_flags)
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

    # Compiled patterns, for the parser. Looked up by (pattern, flags) on every access, so they
    # always match the current field values; validation guarantees they compile.

    def _pattern(self, pattern: str | None) -> re.Pattern[str] | None:
        return _compiled(pattern, self.re_flags) if pattern is not None else None

    @property
    def detect_re(self) -> re.Pattern[str] | None:
        return self._pattern(self.detect)

    @property
    def score_re(self) -> re.Pattern[str] | None:
        return self._pattern(self.score.pattern if self.score is not None else None)

    @property
    def puzzle_re(self) -> re.Pattern[str] | None:
        return self._pattern(self.puzzle.pattern if self.puzzle is not None else None)

    @property
    def block_re(self) -> re.Pattern[str] | None:
        return self._pattern(self.rounds.block if self.rounds is not None else None)

    @property
    def item_re(self) -> re.Pattern[str] | None:
        return self._pattern(self.rounds.item if self.rounds is not None else None)

    def tokens(self) -> list[str]:
        """Every word that names this game in commands: its name, aliases and display name."""
        return [self.name, *self.aliases, *([self.display_name] if self.display_name else [])]

    @property
    def label(self) -> str:
        """`display_name`, or `name` when unset."""
        return self.display_name or self.name

    def value_names(self) -> list[str]:
        """`["score", *values]`."""
        return ["score", *self.values]

    def value(self, name: str, score: float, rounds: tuple[float, ...]) -> float | None:
        """Compute a named value from a result; `None` if it can't be computed (e.g. no rounds).

        Raises `KeyError` for a value this game doesn't define.
        """
        if name == "score":
            return score
        return reduce_rounds(self.values[name].from_rounds, rounds)

    def higher_is_better_for(self, value_name: str) -> bool:
        """The value's own direction if it sets one, else the game's."""
        if value_name == "score":
            return self.higher_is_better
        override = self.values[value_name].higher_is_better
        return self.higher_is_better if override is None else override


def reduce_rounds(reducer: Reducer, rounds: tuple[float, ...]) -> float | None:
    """Apply a `from_rounds` reducer; `None` when there are no rounds."""
    if not rounds:
        return None
    match reducer:
        case "sum":
            return float(sum(rounds))
        case "avg":
            return sum(rounds) / len(rounds)
        case "max":
            return float(max(rounds))
        case "min":
            return float(min(rounds))


def parse_number(raw: str | None, spec: NumberSpec) -> float | None:
    """Convert a captured string to a number: apply `spec.map`, strip separators, convert.

    Returns `None` when the value is missing (an optional group that didn't match), can't be
    parsed, or isn't finite (`inf`, `nan`, overflow).
    """
    if raw is None:
        return None
    raw = raw.strip()
    if raw in spec.map:
        return float(spec.map[raw])
    cleaned = re.sub(r"[,_\s]", "", raw)
    try:
        value = float(int(cleaned)) if spec.type == "int" else float(cleaned)
    except (ValueError, OverflowError):
        return None
    return value if math.isfinite(value) else None


def load_games(directory: Path) -> dict[str, GameConfig]:
    """Load, validate and return the enabled games in `directory`, keyed by name.

    Files are read in sorted order; `name` defaults to the file stem. Names, aliases and display
    names are command tokens, so they must be unique across games (case-insensitive). Every error
    is a `ValueError` prefixed with the offending file's path.
    """
    if not directory.is_dir():
        raise ValueError(f"{directory}: games directory not found")

    games: dict[str, GameConfig] = {}
    owners: dict[str, tuple[str, Path]] = {}  # lowercased token → (game name, file)
    for path in sorted([*directory.glob("*.yaml"), *directory.glob("*.yml")]):
        try:
            raw = yaml.safe_load(path.read_text()) or {}
            if not isinstance(raw, dict):
                raise ValueError("expected a mapping at the top level")
            game = GameConfig.model_validate({"name": path.stem} | raw)
        except (yaml.YAMLError, ValueError) as exc:  # pydantic's ValidationError is a ValueError
            raise ValueError(f"{path}: {exc}") from exc
        if not game.enabled:
            continue
        if game.name in games:
            raise ValueError(f"{path}: game {game.name!r} is already defined in {owners[game.name][1]}")

        for token in sorted(set(game.tokens())):
            owner = owners.get(token.lower())
            if owner is not None and owner[0] != game.name:
                raise ValueError(f"{path}: {token!r} is already used by game {owner[0]!r} ({owner[1]})")
            owners[token.lower()] = (game.name, path)
        games[game.name] = game
    return games
