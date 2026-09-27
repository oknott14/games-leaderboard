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


# ── T-603: parse, show, reparse ──


def ingest(config: Path, *texts: str) -> None:
    """Store messages directly in the configured database, as the bot would."""
    from datetime import UTC, datetime, timedelta

    from leaderboard.cli import load_all, make_service
    from leaderboard.ports import ChatMessage
    from leaderboard.settings import Settings

    settings = Settings.from_env()
    games, boards, _ = load_all(settings)
    service = make_service(settings, games, boards, lambda p, u: u)
    service.channel_ids = frozenset({"C1"})
    for i, text in enumerate(texts):
        at = datetime.now(UTC) - timedelta(minutes=len(texts) - i)
        service.on_message(ChatMessage("slack", "C1", str(i), f"U{i}", text, at))


def test_parse_uses_the_configured_games(config: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["parse", "Krillion #72 🦐\n505\n\n🏮🌟🐟🏮🏮🦑🦑"]) == 0
    assert capsys.readouterr().out.startswith("Krillion      score=505  rounds=[85, 100, 30, 85, 85, 60, 60]  puzzle=72")


def test_parse_passes_its_own_flags_through(config: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["parse", "--all-games", "nothing here"]) == 0
    assert "(not detected)" in capsys.readouterr().out


def test_show_prints_the_board_with_user_ids_offline(config: Path, capsys: pytest.CaptureFixture[str]) -> None:
    ingest(config, "Krillion #72 🦐\n505\n\n🏮🌟🐟🏮🏮🦑🦑")
    assert main(["show", "daily", "krillion"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("*Daily results* — ") and "🥇 U0 — 505" in out


def test_show_ad_hoc_and_errors(config: Path, capsys: pytest.CaptureFixture[str]) -> None:
    ingest(config, "Krillion #72 🦐\n505\n\n🏮🌟🐟🏮🏮🦑🦑")
    main(["show", "krillion", "best_round", "best", "all"])
    assert "🥇 U0 — 100" in capsys.readouterr().out
    main(["show", "wekly"])
    assert "Did you mean: `weekly`" in capsys.readouterr().out


def test_show_uses_slack_names_when_a_token_is_set(config: Path, monkeypatch: pytest.MonkeyPatch,
                                                   capsys: pytest.CaptureFixture[str]) -> None:
    from leaderboard import cli

    class FakePort:
        def display_name(self, user_id: str) -> str:
            return {"U0": "Alice"}.get(user_id, user_id)

    ingest(config, "Krillion #72 🦐\n505\n\n🏮🌟🐟🏮🏮🦑🦑")
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setattr(cli, "_slack_port", lambda settings: FakePort())
    main(["show", "daily"])
    assert "🥇 Alice — 505" in capsys.readouterr().out


def test_reparse_prints_the_count(config: Path, capsys: pytest.CaptureFixture[str]) -> None:
    ingest(config, "Krillion #72 🦐\n505\n\n🏮🌟🐟🏮🏮🦑🦑", "lunch?", "TimeGuessr #512 38,532/50,000")
    assert main(["reparse"]) == 0
    assert capsys.readouterr().out.strip() == "Reparsed stored messages: 2 results"


def test_missing_ssl_cert_file_is_a_clear_error(config: Path, monkeypatch: pytest.MonkeyPatch,
                                                capsys: pytest.CaptureFixture[str]) -> None:
    from leaderboard.cli import _ssl_context
    from leaderboard.settings import Settings

    monkeypatch.setenv("SSL_CERT_FILE", str(config / "nope.pem"))
    with pytest.raises(SystemExit):
        _ssl_context(Settings.from_env())
    assert "SSL_CERT_FILE" in capsys.readouterr().err
