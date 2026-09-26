"""Registries of windows, aggregators and board types.

Built-ins and plugins register through the same decorators:

    @aggregator("top3_avg", params=Params, description="Average of the 3 best results")
    def top3_avg(entries: list[Entry], ctx: AggContext) -> float | None: ...
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, TypeAlias, TypeVar

from pydantic import BaseModel

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
    raise NotImplementedError  # T-321


def load_plugins(directory: Path) -> list[str]:
    """Import every plugin in `directory`; return the names they registered."""
    raise NotImplementedError  # T-321


def validate_params(reg: Registered, raw: dict[str, Any]) -> BaseModel | None:
    """Validate a component's params (mapping `__positional__` to its first field)."""
    raise NotImplementedError  # T-321
