from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from leaderboard.cli import main

ROOT = Path(__file__).parents[1]


@pytest.fixture
def config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Copies of the repo's games/ and boards.yaml, pointed at via the environment. Plugins stay
    in the repo's plugins/: a plugin module can only be loaded from one place per process."""
    shutil.copytree(ROOT / "games", tmp_path / "games")
    shutil.copy(ROOT / "boards.yaml", tmp_path / "boards.yaml")
    monkeypatch.setenv("GAMES_DIR", str(tmp_path / "games"))
    monkeypatch.setenv("BOARDS_FILE", str(tmp_path / "boards.yaml"))
    monkeypatch.setenv("PLUGINS_DIR", str(ROOT / "plugins"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    for name in ("SLACK_BOT_TOKEN", "SLACK_APP_TOKEN", "SLACK_CHANNEL_IDS"):
        monkeypatch.delenv(name, raising=False)
    return tmp_path


def test_no_command_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    assert "usage: leaderboard" in capsys.readouterr().out


def test_check_passes_on_the_repo_config(config: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["check"]) == 0
    out = capsys.readouterr().out
    assert "Games (3):" in out and "Boards (11):" in out and "top3_avg" in out
    assert "  weekly        Weekly total (week · sum · score)" in out
    assert out.rstrip().endswith("OK")


@pytest.mark.parametrize(
    ("path", "body", "names"),
    [
        ("games/broken.yaml", "detect: '('\nscore: { pattern: '(?P<value>\\d+)' }\n", "broken.yaml"),
        ("boards.yaml", "boards: { weekly: { window: fortnight } }\n", "boards.yaml"),
        ("bad_plugins/cli_bad_plugin.py", "def oops(:\n", "cli_bad_plugin.py"),
    ],
)
def test_check_exits_2_naming_the_broken_file(config: Path, capsys: pytest.CaptureFixture[str],
                                              monkeypatch: pytest.MonkeyPatch,
                                              path: str, body: str, names: str) -> None:
    if path.startswith("bad_plugins/"):
        (config / "bad_plugins").mkdir()
        monkeypatch.setenv("PLUGINS_DIR", str(config / "bad_plugins"))
    (config / path).write_text(body)
    with pytest.raises(SystemExit) as exit_info:
        main(["check"])
    assert exit_info.value.code == 2
    assert names in capsys.readouterr().err


def test_check_works_without_slack_tokens(config: Path) -> None:
    assert main(["check"]) == 0  # no SLACK_* variables are set by the fixture


def test_log_level_flag(config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import logging

    seen: dict = {}
    monkeypatch.setattr(logging, "basicConfig", lambda **kw: seen.update(kw))
    main(["--log-level", "DEBUG", "check"])
    assert seen["level"] == "DEBUG"
