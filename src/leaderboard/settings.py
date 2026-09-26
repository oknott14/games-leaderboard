"""Runtime settings, read from environment variables. See docs/plan/06-runtime.md."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Settings:
    slack_bot_token: str
    slack_app_token: str
    channel_ids: frozenset[str]
    timezone: ZoneInfo
    database_url: str = "sqlite:///data/leaderboard.db"
    games_dir: Path = Path("games")
    boards_file: Path = Path("boards.yaml")
    plugins_dir: Path = Path("plugins")
    backfill_days: int = 90
    store_non_game_messages: bool = True
    https_proxy: str | None = None
    ssl_cert_file: Path | None = None
    log_level: str = "INFO"

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> Settings:
        raise NotImplementedError  # T-601
