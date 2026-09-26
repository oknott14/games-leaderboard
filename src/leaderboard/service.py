"""`LeaderboardService`: the one object chat adapters talk to.

Stores messages, keeps parsed results in sync with edits and deletes, and answers commands.
See docs/plan/02-persistence-service.md.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from leaderboard.models import GameResult, GameRound, Message
from leaderboard.parser import parse_message

if TYPE_CHECKING:
    from leaderboard.boards.config import BoardsFile
    from leaderboard.boards.engine import BoardResult
    from leaderboard.commands import Query
    from leaderboard.config import GameConfig
    from leaderboard.formatting import NameFor
    from leaderboard.ports import ChatMessage, ChatPort

log = logging.getLogger(__name__)


def to_db(dt: datetime) -> datetime:
    """Aware datetime → naive UTC, as stored."""
    return dt.astimezone(UTC).replace(tzinfo=None)


def from_db(dt: datetime) -> datetime:
    """Stored naive UTC → aware UTC."""
    return dt.replace(tzinfo=UTC)


def local_date(dt: datetime, tz: ZoneInfo) -> date:
    """The calendar date of an aware (or stored naive-UTC) datetime in `tz`."""
    aware = dt if dt.tzinfo is not None else from_db(dt)
    return aware.astimezone(tz).date()


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
        self.sessions = sessions
        self.games = games
        self.boards = boards
        self.tz = tz
        self.channel_ids = channel_ids
        self.name_for = name_for
        self.store_non_game = store_non_game
        self._today = today or (lambda: datetime.now(tz).date())

    def today(self) -> date:
        return self._today()

    # ── ingest ──

    def on_message(self, msg: ChatMessage) -> None:
        """Store a new or edited message and replace its parsed results. Idempotent."""
        if msg.channel_id not in self.channel_ids:
            return
        results = parse_message(msg.text, self.games.values())

        with self.sessions.begin() as session:
            row = self._find(session, msg.platform, msg.channel_id, msg.message_id)
            if row is None:
                if not results and not self.store_non_game:
                    return
                row = Message(platform=msg.platform, channel_id=msg.channel_id, message_id=msg.message_id,
                              user_id=msg.user_id, text=msg.text, posted_at=to_db(msg.posted_at),
                              thread_id=msg.thread_id)
                session.add(row)
            else:
                if not results and not self.store_non_game:
                    session.delete(row)  # edited into a non-game message
                    return
                if row.text != msg.text:
                    row.edited_at = to_db(datetime.now(UTC))
                row.text, row.user_id, row.thread_id = msg.text, msg.user_id, msg.thread_id
                row.results.clear()
                session.flush()  # delete old results before inserting new ones (unique per game)

            played_on = local_date(msg.posted_at, self.tz)
            for parsed in results:
                result = GameResult(game=parsed.game, platform=msg.platform, user_id=msg.user_id,
                                    score=parsed.score, puzzle=parsed.puzzle, played_on=played_on,
                                    posted_at=row.posted_at)
                result.rounds = [GameRound(round_no=i, value=v) for i, v in enumerate(parsed.rounds, 1)]
                row.results.append(result)

    def on_message_deleted(self, platform: str, channel_id: str, message_id: str) -> None:
        with self.sessions.begin() as session:
            row = self._find(session, platform, channel_id, message_id)
            if row is not None:
                session.delete(row)

    @staticmethod
    def _find(session: Session, platform: str, channel_id: str, message_id: str) -> Message | None:
        return session.scalar(
            select(Message).where(
                Message.platform == platform, Message.channel_id == channel_id, Message.message_id == message_id
            )
        )

    # ── not yet implemented ──

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
