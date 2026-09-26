"""`LeaderboardService`: the one object chat adapters talk to.

Stores messages, keeps parsed results in sync with edits and deletes, and answers commands.
See docs/plan/02-persistence-service.md.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date, datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session, sessionmaker

if TYPE_CHECKING:
    from leaderboard.boards.config import BoardsFile
    from leaderboard.boards.engine import BoardResult
    from leaderboard.commands import Query
    from leaderboard.config import GameConfig
    from leaderboard.formatting import NameFor
    from leaderboard.ports import ChatMessage, ChatPort


class LeaderboardService:
    """Satisfies `ChatHandler`."""

    def __init__(
        self,
        sessions: sessionmaker[Session],
        games: Mapping[str, GameConfig],
        boards: BoardsFile,
        tz: ZoneInfo,
        channel_ids: frozenset[str],
        name_for: NameFor,
        *,
        store_non_game: bool = True,
        today: Callable[[], date] | None = None,
    ) -> None:
        raise NotImplementedError  # T-202

    def on_message(self, msg: ChatMessage) -> None:
        raise NotImplementedError  # T-202

    def on_message_deleted(self, platform: str, channel_id: str, message_id: str) -> None:
        raise NotImplementedError  # T-202

    def on_command(self, text: str) -> str:
        raise NotImplementedError  # T-206

    def run_query(self, query: Query) -> BoardResult:
        raise NotImplementedError  # T-205

    def backfill(self, port: ChatPort, *, since: datetime | None = None, default_days: int = 90) -> int:
        raise NotImplementedError  # T-204

    def reparse(self) -> int:
        raise NotImplementedError  # T-203

    def latest_posted_at(self, platform: str, channel_id: str) -> datetime | None:
        raise NotImplementedError  # T-204
