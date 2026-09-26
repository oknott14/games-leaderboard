"""`boards.yaml` schema: saved leaderboards and the auto-post schedule.

Schema only. Checking references against the registries and games is `load_boards` (T-322).
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

if TYPE_CHECKING:
    from leaderboard.config import GameConfig

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
    """Load `boards.yaml` and validate it against the registries and `games`."""
    raise NotImplementedError  # T-322
