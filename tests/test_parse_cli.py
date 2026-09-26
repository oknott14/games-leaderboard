from __future__ import annotations

import io
from pathlib import Path

import pytest
import yaml
from conftest import SAMPLES, sample_games

from leaderboard.parse_cli import parse_main


@pytest.fixture
def games_dir(tmp_path: Path) -> Path:
    for name, game in sample_games().items():
        body = game.model_dump(exclude_defaults=True, exclude={"name"})
        (tmp_path / f"{name}.yaml").write_text(yaml.safe_dump(body, allow_unicode=True, sort_keys=False))
    return tmp_path


def run(games_dir: Path, *args: str, stdin: str = "") -> tuple[int, str]:
    out = io.StringIO()
    code = parse_main(["--games-dir", str(games_dir), *args], stdin=io.StringIO(stdin), out=out)
    return code, out.getvalue()


def test_maptap_output_format(games_dir: Path) -> None:
    code, out = run(games_dir, SAMPLES["maptap_basic"])
    assert code == 0
    assert out == (
        "MapTap        score=862  rounds=[93, 88, 71, 97, 85]  puzzle=-\n"
        "              best_round=97  worst_round=71  round_avg=86.8\n"
    )


def test_reads_stdin_when_no_argument(games_dir: Path) -> None:
    code, out = run(games_dir, stdin=SAMPLES["krillion_basic"])
    assert code == 0
    assert out.startswith("Krillion      score=505  rounds=[85, 100, 30, 85, 85, 60, 60]  puzzle=72\n")


def test_game_without_extra_values_is_one_line(games_dir: Path) -> None:
    _, out = run(games_dir, SAMPLES["timeguessr_basic"])
    assert out == "TimeGuessr    score=38532  rounds=-  puzzle=512\n"


def test_multiple_games(games_dir: Path) -> None:
    _, out = run(games_dir, SAMPLES["two_games_one_message"])
    assert "TimeGuessr    score=38532" in out and "Krillion      score=505" in out


def test_no_game_detected(games_dir: Path) -> None:
    assert run(games_dir, SAMPLES["not_a_game"]) == (0, "No game detected.\n")


def test_all_games_lists_undetected(games_dir: Path) -> None:
    _, out = run(games_dir, "--all-games", SAMPLES["krillion_basic"])
    assert "MapTap        (not detected)" in out and "TimeGuessr    (not detected)" in out


def test_invalid_config_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "bad.yaml").write_text("detect: '('\n")
    assert run(tmp_path, "x")[0] == 2
    assert "bad.yaml" in capsys.readouterr().err


def test_notes_missing_normalisation(games_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run(games_dir, "x")
    err = capsys.readouterr().err
    # Until T-501 lands the adapter raises NotImplementedError; afterwards there's no note.
    assert err == "" or "normalisation isn't implemented yet" in err


def test_long_labels_keep_a_gap(tmp_path: Path) -> None:
    (tmp_path / "wordle.yaml").write_text(
        "display_name: Wordle Unlimited Deluxe\ndetect: Wordle\nscore: { pattern: 'Wordle (?P<value>\\d+)' }\n"
    )
    _, out = run(tmp_path, "Wordle 5")
    assert out == "Wordle Unlimited Deluxe  score=5  rounds=-  puzzle=-\n"


def test_plugin_games_load_from_plugins_dir(tmp_path: Path) -> None:
    (tmp_path / "games").mkdir()
    (tmp_path / "plugins").mkdir()
    (tmp_path / "plugins" / "cli_plugin_ok.py").write_text(
        "from leaderboard.parser import ParsedResult\n"
        "def parse(text):\n    return ParsedResult('x', 7) if 'Seven' in text else None\n"
    )
    (tmp_path / "games" / "seven.yaml").write_text("parser: cli_plugin_ok:parse\n")
    out = io.StringIO()
    code = parse_main(["--games-dir", str(tmp_path / "games"), "--plugins-dir", str(tmp_path / "plugins"),
                       "Seven!"], stdin=io.StringIO(), out=out)
    assert (code, out.getvalue()) == (0, "seven         score=7  rounds=-  puzzle=-\n")


def test_unloadable_plugin_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "seven.yaml").write_text("parser: cli_plugin_missing_xyz:parse\n")
    assert run(tmp_path, "x")[0] == 2
    assert "can't load parser" in capsys.readouterr().err
