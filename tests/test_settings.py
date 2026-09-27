from __future__ import annotations

from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from leaderboard.settings import Settings


def test_defaults_with_empty_environment() -> None:
    s = Settings.from_env({})
    assert (s.slack_bot_token, s.slack_app_token, s.channel_ids) == ("", "", frozenset())
    assert s.timezone == ZoneInfo("UTC")
    assert s.database_url == "sqlite:///data/leaderboard.db"
    assert (s.games_dir, s.boards_file, s.plugins_dir) == (Path("games"), Path("boards.yaml"), Path("plugins"))
    assert (s.backfill_days, s.store_non_game_messages, s.https_proxy, s.ssl_cert_file, s.log_level) == \
        (90, True, None, None, "INFO")


def test_full_environment() -> None:
    s = Settings.from_env({
        "SLACK_BOT_TOKEN": "xoxb-1", "SLACK_APP_TOKEN": "xapp-1", "SLACK_CHANNEL_IDS": " C1, C2 ,,C1",
        "TIMEZONE": "America/New_York", "DATABASE_URL": "sqlite:///tmp/x.db", "GAMES_DIR": "/cfg/games",
        "BOARDS_FILE": "/cfg/boards.yaml", "PLUGINS_DIR": "/cfg/plugins", "BACKFILL_DAYS": "30",
        "STORE_NON_GAME_MESSAGES": "no", "HTTPS_PROXY": "http://proxy:8080", "SSL_CERT_FILE": "/app/corp-ca.pem",
        "LOG_LEVEL": "debug",
    })
    assert s.channel_ids == frozenset({"C1", "C2"})
    assert s.timezone == ZoneInfo("America/New_York")
    assert (s.games_dir, s.plugins_dir) == (Path("/cfg/games"), Path("/cfg/plugins"))
    assert (s.backfill_days, s.store_non_game_messages, s.log_level) == (30, False, "DEBUG")
    assert (s.https_proxy, s.ssl_cert_file) == ("http://proxy:8080", Path("/app/corp-ca.pem"))


def test_blank_values_fall_back_to_defaults() -> None:
    s = Settings.from_env({"TIMEZONE": "  ", "BACKFILL_DAYS": "", "HTTPS_PROXY": " "})
    assert (s.timezone, s.backfill_days, s.https_proxy) == (ZoneInfo("UTC"), 90, None)


@pytest.mark.parametrize(("raw", "expected"), [("true", True), ("Yes", True), ("1", True), ("off", False), ("FALSE", False)])
def test_booleans(raw: str, expected: bool) -> None:
    assert Settings.from_env({"STORE_NON_GAME_MESSAGES": raw}).store_non_game_messages is expected


@pytest.mark.parametrize(
    ("env", "message"),
    [
        ({"TIMEZONE": "Mars/Olympus"}, "Unknown TIMEZONE 'Mars/Olympus'"),
        ({"BACKFILL_DAYS": "lots"}, "BACKFILL_DAYS must be a whole number"),
        ({"BACKFILL_DAYS": "0"}, "BACKFILL_DAYS must be a whole number"),
        ({"STORE_NON_GAME_MESSAGES": "maybe"}, "STORE_NON_GAME_MESSAGES must be true or false"),
    ],
)
def test_invalid_values_name_the_variable(env: dict, message: str) -> None:
    with pytest.raises(SystemExit, match=message):
        Settings.from_env(env)


def test_require_names_the_missing_variables() -> None:
    s = Settings.from_env({"SLACK_BOT_TOKEN": "xoxb-1"})
    s.require("SLACK_BOT_TOKEN")
    with pytest.raises(SystemExit, match=r"^Missing SLACK_APP_TOKEN, SLACK_CHANNEL_IDS \(see .env.example\)$"):
        s.require("SLACK_BOT_TOKEN", "SLACK_APP_TOKEN", "SLACK_CHANNEL_IDS")


@pytest.mark.parametrize("raw", ["²", "٣", "1.5", "-3"])
def test_backfill_days_rejects_non_ascii_and_non_integers(raw: str) -> None:
    with pytest.raises(SystemExit, match="BACKFILL_DAYS"):
        Settings.from_env({"BACKFILL_DAYS": raw})


def test_log_level_is_validated() -> None:
    assert Settings.from_env({"LOG_LEVEL": "debug"}).log_level == "DEBUG"
    with pytest.raises(SystemExit, match="LOG_LEVEL must be one of"):
        Settings.from_env({"LOG_LEVEL": "verbose"})
