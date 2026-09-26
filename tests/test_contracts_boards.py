from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import FrozenInstanceError
from datetime import date
from pathlib import Path

import pytest
import yaml
from pydantic import BaseModel, ValidationError

import leaderboard.boards as boards_api
from leaderboard.boards import registry
from leaderboard.boards.config import POSITIONAL, BoardConfig, BoardsFile, ComponentRef
from leaderboard.boards.core import DateRange, Standing, WindowResult, dedupe_daily, rank
from leaderboard.boards.engine import board_applies, board_range, board_unit, run_board

ENGINE_DOC = Path(__file__).parents[1] / "docs" / "plan" / "03-boards-engine.md"


@pytest.fixture(autouse=True)
def isolated_registries() -> Iterator[None]:
    """Registrations made by a test don't leak into other tests."""
    saved = [(reg, dict(reg)) for reg in (registry.WINDOWS, registry.AGGREGATORS, registry.BOARD_TYPES)]
    yield
    for reg, contents in saved:
        reg.clear()
        reg.update(contents)


def starter_boards_yaml() -> dict:
    (block,) = re.findall(r"```yaml\n(defaults:.*?)```", ENGINE_DOC.read_text(), re.S)
    return yaml.safe_load(block)


# ── decorators ──


class KParams(BaseModel):
    k: int = 3


def test_decorators_register_and_return_the_function() -> None:
    @registry.aggregator("t_top_k", params=KParams, description="d", unit="pts", higher_is_better=True)
    def top_k(entries, ctx):  # noqa: ANN001, ANN202
        return None

    reg = registry.AGGREGATORS["t_top_k"]
    assert reg.fn is top_k
    assert (reg.params, reg.description, reg.unit, reg.higher_is_better) == (KParams, "d", "pts", True)


@pytest.mark.parametrize(
    ("decorator", "table"),
    [
        (registry.window, registry.WINDOWS),
        (registry.aggregator, registry.AGGREGATORS),
        (registry.board_type, registry.BOARD_TYPES),
    ],
)
def test_each_kind_has_its_own_registry(decorator, table) -> None:  # noqa: ANN001
    decorator("t_thing")(lambda *a: None)
    tables = (registry.WINDOWS, registry.AGGREGATORS, registry.BOARD_TYPES)
    assert [("t_thing" in t) for t in tables] == [t is table for t in tables]


def test_duplicate_name_rejected() -> None:
    registry.window("t_dup")(lambda *a: None)
    with pytest.raises(ValueError, match="already registered"):
        registry.window("t_dup")


@pytest.mark.parametrize("name", ["Top3", "top-3", "top 3", ""])
def test_component_names_must_be_slugs(name: str) -> None:
    with pytest.raises(ValueError, match="must match"):
        registry.aggregator(name)


def test_public_plugin_api() -> None:
    assert set(boards_api.__all__) == {
        "window", "aggregator", "board_type", "Entry", "Standing",
        "BoardContext", "AggContext", "WindowResult", "DateRange",
    }


# ── ComponentRef shorthand ──


@pytest.mark.parametrize(
    ("raw", "name", "params"),
    [
        ("avg", "avg", {}),
        ({"name": "top_k_avg", "k": 3}, "top_k_avg", {"k": 3}),
        ({"k": 3, "name": "top_k_avg"}, "top_k_avg", {"k": 3}),  # key order doesn't matter
        ({"top_k_avg": {"k": 3}}, "top_k_avg", {"k": 3}),
        ({"last_n": 5}, "last_n", {POSITIONAL: 5}),
        ({"all": None}, "all", {}),
        ({"name": "last_n", "params": {"n": 5}}, "last_n", {"n": 5}),  # canonical form
    ],
)
def test_component_shorthand(raw: object, name: str, params: dict) -> None:
    ref = ComponentRef.model_validate(raw)
    assert (ref.name, ref.params) == (name, params)


@pytest.mark.parametrize("raw", [{"avg": 1, "sum": 2}, {"name": "x", "params": {}, "k": 3}, 5])
def test_component_bad_forms_rejected(raw: object) -> None:
    with pytest.raises(ValidationError):
        ComponentRef.model_validate(raw)


# ── BoardConfig / BoardsFile ──


def test_board_defaults() -> None:
    board = BoardConfig(name="b")
    assert (board.type.name, board.window.name, board.aggregate.name) == ("ranked", "week", "sum")
    assert (board.value, board.min_entries, board.limit, board.games) == ("score", 1, 10, None)


def test_starter_boards_yaml_validates() -> None:
    parsed = BoardsFile.model_validate(starter_boards_yaml())
    assert parsed.boards["weekly"].name == "weekly"
    assert parsed.boards["recent_form"].window.params == {POSITIONAL: 5}
    assert parsed.boards["wins"].type.name == "daily_wins"
    assert parsed.boards["top_round"].value == "best_round"
    assert [e.anchor for e in parsed.schedule] == ["yesterday", "last_week"]


@pytest.mark.parametrize(
    "raw",
    [
        {"boards": {"b": {"windw": "week"}}},  # typo
        {"boards": {"b": {"min_entries": 0}}},
        {"schedule": [{"cron": "0 9 * * *", "boards": ["b"], "anchor": "tomorrow"}]},
        {"bords": {}},
    ],
)
def test_boards_file_rejects_bad_input(raw: dict) -> None:
    with pytest.raises(ValidationError):
        BoardsFile.model_validate(raw)


# ── core types & stubs ──


def test_core_types_are_frozen() -> None:
    standing = Standing(player=("slack", "U1"), value=505, entries=1, rank=1)
    assert standing.detail is None
    with pytest.raises(FrozenInstanceError):
        standing.rank = 2  # type: ignore[misc]
    assert WindowResult(DateRange(None, date(2026, 9, 24))).select is None


def test_logic_is_stubbed() -> None:
    board, day = BoardConfig(name="b"), date(2026, 9, 24)
    for call in (
        lambda: dedupe_daily([], "first", True),
        lambda: rank([], True),
        lambda: board_range(board, day),
        lambda: board_unit(board),
        lambda: board_applies(board, None),  # type: ignore[arg-type]
        lambda: run_board(board, None, day, lambda r: []),  # type: ignore[arg-type]
        registry.load_builtins,
        lambda: registry.load_plugins(Path(".")),
    ):
        with pytest.raises(NotImplementedError):
            call()
