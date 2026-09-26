from __future__ import annotations

import importlib
import re
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import BaseModel

from leaderboard.boards.config import POSITIONAL
from leaderboard.boards.registry import AGGREGATORS, BOARD_TYPES, WINDOWS, Registered, load_builtins, load_plugins, validate_params


@pytest.fixture(autouse=True)
def isolated_registries() -> Iterator[None]:
    load_builtins()  # snapshot includes the built-ins
    saved = [(reg, dict(reg)) for reg in (WINDOWS, AGGREGATORS, BOARD_TYPES)]
    path = list(sys.path)
    yield
    for reg, contents in saved:
        reg.clear()
        reg.update(contents)
    sys.path[:] = path


@pytest.fixture
def plugins_dir(tmp_path: Path, request: pytest.FixtureRequest) -> tuple[Path, str]:
    """A plugins dir plus a per-test module prefix (sys.modules caches plugin modules by name)."""
    return tmp_path, "p_" + re.sub(r"\W", "_", request.node.name)


def test_load_builtins_is_idempotent() -> None:
    load_builtins()
    load_builtins()
    assert {"day", "week", "last_n"} <= set(WINDOWS)
    assert {"sum", "streak", "top_k_avg"} <= set(AGGREGATORS)
    assert {"ranked", "daily_wins", "improvement"} <= set(BOARD_TYPES)


def test_load_plugins_registers_and_reports_names(plugins_dir: tuple[Path, str]) -> None:
    directory, prefix = plugins_dir
    (directory / f"{prefix}_a.py").write_text(
        "from leaderboard.boards import aggregator, window\n"
        f"@aggregator('{prefix}_agg')\ndef a(entries, ctx): return None\n"
        f"@window('{prefix}_win')\ndef w(anchor, params): return None\n"
    )
    (directory / "_private.py").write_text("raise RuntimeError('must be skipped')\n")
    (directory / "notes.txt").write_text("ignored")
    assert sorted(load_plugins(directory)) == [f"{prefix}_agg", f"{prefix}_win"]
    assert f"{prefix}_agg" in AGGREGATORS and str(directory) in sys.path


def test_plugin_is_importable_by_plain_name_like_parser_refs(plugins_dir: tuple[Path, str]) -> None:
    directory, prefix = plugins_dir
    (directory / f"{prefix}.py").write_text(f"from leaderboard.boards import aggregator\n@aggregator('{prefix}')\ndef a(e, c): return 1\n")
    load_plugins(directory)
    importlib.import_module(prefix)  # a parser ref to the same module doesn't re-register
    assert load_plugins(directory) == []  # second load: already imported, nothing new


def test_missing_plugins_dir(tmp_path: Path) -> None:
    assert load_plugins(tmp_path / "nope") == []


def test_plugin_error_names_the_file(plugins_dir: tuple[Path, str]) -> None:
    directory, prefix = plugins_dir
    bad = directory / f"{prefix}.py"
    bad.write_text("def broken(:\n")
    with pytest.raises(RuntimeError, match=rf"plugin {re.escape(str(bad))}: SyntaxError"):
        load_plugins(directory)


def test_plugin_duplicate_name_is_an_error(plugins_dir: tuple[Path, str]) -> None:
    directory, prefix = plugins_dir
    (directory / f"{prefix}.py").write_text("from leaderboard.boards import aggregator\n@aggregator('sum')\ndef s(e, c): return 0\n")
    with pytest.raises(RuntimeError, match="aggregator 'sum' is already registered"):
        load_plugins(directory)


# ── validate_params ──


class NParams(BaseModel):
    n: int
    label: str = "x"


WITH = Registered("with_params", lambda: None, NParams, "", None, None)
WITHOUT = Registered("no_params", lambda: None, None, "", None, None)


def test_positional_fills_the_first_field() -> None:
    params = validate_params(WITH, {POSITIONAL: 5})
    assert isinstance(params, NParams) and (params.n, params.label) == (5, "x")


def test_named_params() -> None:
    assert validate_params(WITH, {"n": 3, "label": "y"}) == NParams(n=3, label="y")


def test_positional_and_named_first_field_conflict() -> None:
    with pytest.raises(ValueError, match="'n' given twice"):
        validate_params(WITH, {POSITIONAL: 5, "n": 6})


def test_invalid_params_name_the_component() -> None:
    with pytest.raises(ValueError, match="with_params: invalid parameters"):
        validate_params(WITH, {"n": "lots"})


def test_component_without_params() -> None:
    assert validate_params(WITHOUT, {}) is None
    with pytest.raises(ValueError, match=r"no_params takes no parameters, got \['k'\]"):
        validate_params(WITHOUT, {"k": 1})


def test_builtin_shorthand_round_trip() -> None:
    assert validate_params(WINDOWS["last_n"], {POSITIONAL: 5}).n == 5  # type: ignore[union-attr]
    assert validate_params(AGGREGATORS["top_k_avg"], {"k": 3}).k == 3  # type: ignore[union-attr]
