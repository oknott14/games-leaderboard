"""The repo's real boards.yaml and example plugin, loaded with the real registries."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest
import yaml
from conftest import make_board, make_rows, sample_games

from leaderboard.boards.config import load_boards
from leaderboard.boards.engine import run_board
from leaderboard.boards.registry import AGGREGATORS, load_builtins, load_plugins

ROOT = Path(__file__).parents[1]
ENGINE_DOC = ROOT / "docs" / "plan" / "03-boards-engine.md"


@pytest.fixture(scope="module", autouse=True)
def registries() -> None:
    load_builtins()
    load_plugins(ROOT / "plugins")


def test_example_plugin_registers_top3_avg() -> None:
    assert "top3_avg" in AGGREGATORS
    assert AGGREGATORS["top3_avg"].description


def test_starter_boards_yaml_loads() -> None:
    parsed = load_boards(ROOT / "boards.yaml", sample_games())
    assert list(parsed.boards) == [
        "daily", "weekly", "average", "top_score", "recent_form", "latest_scores",
        "streaks", "consistency", "wins", "most_improved", "top_round",
    ]
    assert [(e.cron, e.boards, e.anchor) for e in parsed.schedule] == [
        ("0 9 * * *", ["daily"], "yesterday"),
        ("0 9 * * MON", ["weekly", "recent_form", "wins"], "last_week"),
    ]


def test_starter_boards_match_the_plan_doc() -> None:
    (block,) = re.findall(r"```yaml\n(defaults:.*?)```", ENGINE_DOC.read_text(), re.S)
    assert yaml.safe_load((ROOT / "boards.yaml").read_text()) == yaml.safe_load(block)


def test_boards_using_the_plugin_validate(tmp_path: Path) -> None:
    path = tmp_path / "boards.yaml"
    path.write_text("boards:\n  top3: { window: month, aggregate: top3_avg }\n"
                    "  top2: { window: month, aggregate: { top3_avg: 2 } }\n")
    parsed = load_boards(path, sample_games())
    assert parsed.boards["top2"].aggregate.params == {"__positional__": 2}


@pytest.mark.parametrize(("aggregate", "expected"), [("top3_avg", 80.0), ({"top3_avg": 2}, 90.0)])
def test_plugin_runs_through_the_engine(aggregate: object, expected: float) -> None:
    rows = make_rows([("a", f"2026-09-{d:02d}", v) for d, v in [(1, 100), (2, 80), (3, 60), (4, 10)]],
                     game="timeguessr")
    board = make_board(window="month", aggregate=aggregate)
    (standing,) = run_board(board, sample_games()["timeguessr"], date(2026, 9, 24),
                            lambda rng: [r for r in rows if r.played_on <= rng.end])
    assert standing.value == expected


def test_example_plugin_rejects_misspelled_params(tmp_path: Path) -> None:
    path = tmp_path / "boards.yaml"
    path.write_text("boards:\n  top3: { aggregate: { top3_avg: { n: 5 } } }\n")
    with pytest.raises(ValueError, match="unknown parameter"):
        load_boards(path, sample_games())
