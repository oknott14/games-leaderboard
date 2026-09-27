"""The Slack manifest grants exactly what the adapter uses."""

from __future__ import annotations

from pathlib import Path

import yaml

MANIFEST = yaml.safe_load((Path(__file__).parents[1] / "slack-manifest.yaml").read_text())


def test_socket_mode_and_internal() -> None:
    settings = MANIFEST["settings"]
    assert settings["socket_mode_enabled"] is True
    assert settings["org_deploy_enabled"] is False
    assert settings["token_rotation_enabled"] is False


def test_minimal_bot_scopes() -> None:
    assert sorted(MANIFEST["oauth_config"]["scopes"]["bot"]) == sorted(
        ["groups:history", "chat:write", "users:read", "app_mentions:read", "commands"]
    )


def test_events_match_the_adapter_listeners() -> None:
    # adapters/slack.py listens for `message` (private channels → message.groups) and `app_mention`
    assert sorted(MANIFEST["settings"]["event_subscriptions"]["bot_events"]) == ["app_mention", "message.groups"]


def test_slash_command_matches_the_adapter() -> None:
    (command,) = MANIFEST["features"]["slash_commands"]
    assert command["command"] == "/leaderboard"
    assert "/leaderboard" in (Path(__file__).parents[1] / "src/leaderboard/adapters/slack.py").read_text()


def test_bot_user() -> None:
    assert MANIFEST["features"]["bot_user"]["display_name"] == "leaderboard"
