"""`boards.yaml`: saved leaderboards and the auto-post schedule (schema and loader)."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

if TYPE_CHECKING:
    from leaderboard.config import GameConfig

log = logging.getLogger(__name__)

POSITIONAL = "__positional__"  # scalar shorthand param, mapped to the first field by validate_params

AnchorName = Literal["today", "yesterday", "last_week", "last_month"]


class ComponentRef(BaseModel):
    """A reference to a window, aggregator or board type, plus its params.

    Accepted YAML forms:
      avg                       → name="avg"
      {name: top_k_avg, k: 3}   → name="top_k_avg", params={"k": 3}
      {top_k_avg: {k: 3}}       → name="top_k_avg", params={"k": 3}
      {last_n: 5}               → name="last_n",    params={"__positional__": 5}
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    params: dict[str, Any] = {}

    @model_validator(mode="before")
    @classmethod
    def _shorthand(cls, raw: Any) -> Any:
        if isinstance(raw, str):
            return {"name": raw}
        if not isinstance(raw, dict):
            return raw
        if "name" in raw:
            if "params" in raw:
                return raw  # explicit form; extra keys are rejected by extra="forbid"
            return {"name": raw["name"], "params": {k: v for k, v in raw.items() if k != "name"}}
        if len(raw) != 1:
            raise ValueError(f"expected a name or a single-key mapping, got keys {sorted(raw)}")
        ((name, value),) = raw.items()
        if value is None:
            return {"name": name}
        if isinstance(value, dict):
            return {"name": name, "params": value}
        return {"name": name, "params": {POSITIONAL: value}}


class BoardConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    title: str | None = None
    type: ComponentRef = ComponentRef(name="ranked")
    value: str = "score"
    window: ComponentRef = ComponentRef(name="week")
    aggregate: ComponentRef = ComponentRef(name="sum")
    min_entries: int = Field(default=1, ge=1)
    higher_is_better: bool | None = None
    games: list[str] | None = None  # None = every game that has `value`
    limit: int = Field(default=10, ge=1)


class ScheduleEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cron: str  # 5-field crontab
    boards: list[str]
    anchor: AnchorName = "today"


class BoardsFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    defaults: dict[str, Any] = {}  # merged under every board by load_boards
    boards: dict[str, BoardConfig] = {}
    schedule: list[ScheduleEntry] = []

    @model_validator(mode="before")
    @classmethod
    def _board_names_from_keys(cls, raw: Any) -> Any:
        """Boards are keyed by name in YAML; copy each key into the board's `name`."""
        if isinstance(raw, dict) and isinstance(raw.get("boards"), dict):
            boards = {
                key: ({"name": key} | board) if isinstance(board, dict) else board
                for key, board in raw["boards"].items()
            }
            raw = raw | {"boards": boards}
        return raw


def load_boards(path: Path, games: Mapping[str, GameConfig]) -> BoardsFile:
    """Load `boards.yaml` and validate it against the registries and `games`.

    `defaults` are merged under every board. The registries must already hold the built-ins and
    plugins (`load_builtins`, `load_plugins`). A missing file gives an empty `BoardsFile`. Every
    error is a `ValueError` starting with the file name (and the board, where there is one).
    """
    if not path.exists():
        log.warning("%s not found: no saved boards or schedule", path)
        return BoardsFile()
    try:
        raw = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"{path.name}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"{path.name}: expected a mapping at the top level")

    defaults = raw.get("defaults") or {}
    boards = raw.get("boards") or {}
    if not isinstance(defaults, dict) or not isinstance(boards, dict):
        raise ValueError(f"{path.name}: `defaults` and `boards` must be mappings")
    merged = {name: defaults | (body or {}) for name, body in boards.items()}
    try:
        parsed = BoardsFile.model_validate(raw | {"boards": merged})
    except ValidationError as exc:
        raise ValueError(f"{path.name}: {exc}") from None

    for name, board in parsed.boards.items():
        try:
            _check_board(board, games)
        except ValueError as exc:
            raise ValueError(f"{path.name}: board {name!r}: {exc}") from None
    for i, entry in enumerate(parsed.schedule):
        try:
            _check_schedule_entry(entry, parsed.boards)
        except ValueError as exc:
            raise ValueError(f"{path.name}: schedule[{i}]: {exc}") from None
    try:
        check_token_collisions(parsed.boards, games)
    except ValueError as exc:
        raise ValueError(f"{path.name}: {exc}") from None
    return parsed


def check_token_collisions(boards: Mapping[str, BoardConfig], games: Mapping[str, GameConfig]) -> None:
    """Every word a chat command can contain must mean one thing, so commands parse unambiguously.

    Board names, game names/aliases/display names, value names, aggregator and window names,
    anchor words and reserved command words must be distinct (case-insensitive). The same value
    name in several games is fine: it means the same thing.
    """
    from leaderboard.boards.registry import AGGREGATORS, WINDOWS  # (circular)
    from leaderboard.commands import ANCHOR_WORDS, RESERVED_WORDS

    owners: dict[str, str] = {}

    def claim(token: str, owner: str) -> None:
        key = token.lower()
        if key in owners and owners[key] != owner:
            raise ValueError(f"name collision: {token!r} is both {owners[key]} and {owner}")
        owners[key] = owner

    for word in RESERVED_WORDS:
        claim(word, "a reserved command word")
    for word in ANCHOR_WORDS:
        claim(word, "an anchor word")
    for name in WINDOWS:
        claim(name, f"window {name!r}")
    for name in AGGREGATORS:
        claim(name, f"aggregator {name!r}")
    for game in games.values():
        for token in {game.name, *game.aliases, *([game.display_name] if game.display_name else [])}:
            claim(token, f"game {game.name!r}")
    for game in games.values():
        for value in game.value_names():
            claim(value, f"value {value!r}")
    for name in boards:
        claim(name, f"board {name!r}")


def _check_board(board: BoardConfig, games: Mapping[str, GameConfig]) -> None:
    from leaderboard.boards.registry import AGGREGATORS, BOARD_TYPES, WINDOWS, validate_params  # (circular)

    for kind, table, ref in (("type", BOARD_TYPES, board.type), ("window", WINDOWS, board.window),
                             ("aggregate", AGGREGATORS, board.aggregate)):
        if ref.name not in table:
            raise ValueError(f"unknown {kind} {ref.name!r} (available: {', '.join(sorted(table))})")
        validate_params(table[ref.name], ref.params)

    if board.games is not None:
        unknown = [g for g in board.games if g not in games]
        if unknown:
            raise ValueError(f"unknown game(s) {unknown}")
        missing = [g for g in board.games if board.value not in games[g].value_names()]
        if missing:
            raise ValueError(f"value {board.value!r} isn't defined by {missing}")
    elif not any(board.value in game.value_names() for game in games.values()):
        raise ValueError(f"no game defines the value {board.value!r}")


def _check_schedule_entry(entry: ScheduleEntry, boards: Mapping[str, BoardConfig]) -> None:
    from apscheduler.triggers.cron import CronTrigger

    unknown = [b for b in entry.boards if b not in boards]
    if unknown:
        raise ValueError(f"unknown board(s) {unknown}")
    try:
        CronTrigger.from_crontab(entry.cron)
    except ValueError as exc:
        raise ValueError(f"invalid cron {entry.cron!r}: {exc}") from None
