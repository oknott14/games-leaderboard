"""Runtime settings, read from environment variables. See docs/plan/06-runtime.md."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


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
        """Read settings from environment variables (see .env.example).

        Slack values may be empty here: commands that need them call `require`. Invalid values
        exit with a message naming the variable.
        """

        def get(name: str, default: str = "") -> str:
            return (env.get(name) or "").strip() or default

        timezone = get("TIMEZONE", "UTC")
        try:
            tz = ZoneInfo(timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise SystemExit(f"Unknown TIMEZONE {timezone!r}; use an IANA name like America/New_York") from None

        backfill = get("BACKFILL_DAYS", "90")
        if not backfill.isascii() or not backfill.isdecimal() or int(backfill) < 1:
            raise SystemExit(f"BACKFILL_DAYS must be a whole number of days >= 1, got {backfill!r}")

        log_level = get("LOG_LEVEL", cls.log_level).upper()
        if log_level not in LOG_LEVELS:
            raise SystemExit(f"LOG_LEVEL must be one of {', '.join(LOG_LEVELS)}, got {log_level!r}")

        cert = get("SSL_CERT_FILE")
        return cls(
            slack_bot_token=get("SLACK_BOT_TOKEN"),
            slack_app_token=get("SLACK_APP_TOKEN"),
            channel_ids=frozenset(c.strip() for c in get("SLACK_CHANNEL_IDS").split(",") if c.strip()),
            timezone=tz,
            database_url=get("DATABASE_URL", cls.database_url),
            games_dir=Path(get("GAMES_DIR", str(cls.games_dir))),
            boards_file=Path(get("BOARDS_FILE", str(cls.boards_file))),
            plugins_dir=Path(get("PLUGINS_DIR", str(cls.plugins_dir))),
            backfill_days=int(backfill),
            store_non_game_messages=_boolean("STORE_NON_GAME_MESSAGES", get("STORE_NON_GAME_MESSAGES", "true")),
            https_proxy=get("HTTPS_PROXY") or None,
            ssl_cert_file=Path(cert) if cert else None,
            log_level=log_level,
        )

    def require(self, *names: str) -> None:
        """Exit with a clear message if any of these environment variables weren't set."""
        values = {
            "SLACK_BOT_TOKEN": self.slack_bot_token,
            "SLACK_APP_TOKEN": self.slack_app_token,
            "SLACK_CHANNEL_IDS": self.channel_ids,
        }
        missing = [name for name in names if not values[name]]
        if missing:
            raise SystemExit(f"Missing {', '.join(missing)} (see .env.example)")


def _boolean(name: str, raw: str) -> bool:
    lowered = raw.lower()
    if lowered in ("1", "true", "yes", "on"):
        return True
    if lowered in ("0", "false", "no", "off"):
        return False
    raise SystemExit(f"{name} must be true or false, got {raw!r}")
