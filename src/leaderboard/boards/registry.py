"""Registries of windows, aggregators and board types.

Built-ins and plugins register through the same decorators:

    @aggregator("top3_avg", params=Params, description="Average of the 3 best results")
    def top3_avg(entries: list[Entry], ctx: AggContext) -> float | None: ...
"""

from __future__ import annotations

import importlib
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, TypeAlias, TypeVar

from pydantic import BaseModel, ValidationError

from leaderboard.boards.config import POSITIONAL
from leaderboard.boards.core import AggContext, BoardContext, Entry, Standing, WindowResult

WindowFn: TypeAlias = Callable[[date, BaseModel | None], WindowResult]
AggregatorFn: TypeAlias = Callable[[list[Entry], AggContext], float | None]
BoardTypeFn: TypeAlias = Callable[[BoardContext], list[Standing]]

F = TypeVar("F", bound=Callable[..., Any])

_NAME = re.compile(r"^[a-z0-9_]+$")


@dataclass(frozen=True)
class Registered:
    name: str
    fn: Callable[..., Any]
    params: type[BaseModel] | None
    description: str
    unit: str | None  # display suffix, e.g. "days"
    higher_is_better: bool | None  # forced ranking direction (count → True, stddev → False)


WINDOWS: dict[str, Registered] = {}
AGGREGATORS: dict[str, Registered] = {}
BOARD_TYPES: dict[str, Registered] = {}


def _register(
    registry: dict[str, Registered],
    kind: str,
    name: str,
    params: type[BaseModel] | None,
    description: str,
    unit: str | None,
    higher_is_better: bool | None,
) -> Callable[[F], F]:
    if not _NAME.match(name):
        raise ValueError(f"{kind} name {name!r} must match {_NAME.pattern}")
    if name in registry:
        raise ValueError(f"{kind} {name!r} is already registered")

    def decorator(fn: F) -> F:
        registry[name] = Registered(name, fn, params, description, unit, higher_is_better)
        return fn

    return decorator


def window(name: str, *, params: type[BaseModel] | None = None, description: str = "") -> Callable[[F], F]:
    return _register(WINDOWS, "window", name, params, description, None, None)


def aggregator(
    name: str,
    *,
    params: type[BaseModel] | None = None,
    description: str = "",
    unit: str | None = None,
    higher_is_better: bool | None = None,
) -> Callable[[F], F]:
    return _register(AGGREGATORS, "aggregator", name, params, description, unit, higher_is_better)


def board_type(
    name: str, *, params: type[BaseModel] | None = None, description: str = "", unit: str | None = None
) -> Callable[[F], F]:
    return _register(BOARD_TYPES, "board type", name, params, description, unit, None)


def load_builtins() -> None:
    """Import the built-in windows, aggregators and board types. Idempotent."""
    for module in ("windows", "aggregators", "types"):
        importlib.import_module(f"leaderboard.boards.{module}")


def load_plugins(directory: Path) -> list[str]:
    """Import every plugin in `directory`; return the names they registered.

    Files are imported by their plain module name with `directory` on sys.path, the same way a
    game's `parser: module:function` is resolved, so a module is never executed twice. Files
    starting with `_` are skipped. A failing plugin raises `RuntimeError` naming the file.
    """
    if not directory.is_dir():
        return []
    add_plugins_path(directory)

    before = {id(reg): set(reg) for reg in (WINDOWS, AGGREGATORS, BOARD_TYPES)}
    for path in sorted(directory.glob("*.py")):
        if path.name.startswith("_"):
            continue
        try:
            module = importlib.import_module(path.stem)
        except Exception as exc:
            raise RuntimeError(f"plugin {path}: {type(exc).__name__}: {exc}") from exc
        loaded_from = Path(getattr(module, "__file__", "") or "").resolve()
        if loaded_from != path.resolve():
            raise RuntimeError(
                f"plugin {path}: the name {path.stem!r} is already taken by {loaded_from or 'a built-in module'}; "
                "rename the plugin file"
            )
    return [name for reg in (WINDOWS, AGGREGATORS, BOARD_TYPES) for name in reg if name not in before[id(reg)]]


def add_plugins_path(directory: Path) -> None:
    """Make plugin modules importable by name (for plugins and game `parser:` refs). The path is
    appended, so a plugin can never shadow the standard library or installed packages."""
    path = str(directory.resolve())
    if path not in sys.path:
        sys.path.append(path)


def validate_params(reg: Registered, raw: dict[str, Any]) -> BaseModel | None:
    """Validate a component's params. A scalar shorthand (`{last_n: 5}`, stored under
    `__positional__`) fills the params model's first field. Errors are `ValueError`s naming
    the component."""
    if reg.params is None:
        if raw:
            raise ValueError(f"{reg.name} takes no parameters, got {sorted(raw)}")
        return None
    values = dict(raw)
    if POSITIONAL in values:
        first = next(iter(reg.params.model_fields))
        if first in values:
            raise ValueError(f"{reg.name}: {first!r} given twice")
        values[first] = values.pop(POSITIONAL)
    unknown = sorted(set(values) - set(reg.params.model_fields))
    if unknown:
        raise ValueError(f"{reg.name}: unknown parameter(s) {unknown} (expected: {sorted(reg.params.model_fields)})")
    try:
        return reg.params.model_validate(values)
    except ValidationError as exc:
        raise ValueError(f"{reg.name}: invalid parameters: {exc}") from None
