"""`LeaderboardService`: the one object chat adapters talk to.

Stores messages, keeps parsed results in sync with edits and deletes, and answers commands.
See docs/plan/02-persistence-service.md.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime, timedelta
from functools import partial
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload, sessionmaker

from leaderboard.boards import engine as board_engine
from leaderboard.boards.core import DateRange, ResultRow
from leaderboard.models import GameResult, GameRound, Message
from leaderboard.parser import ParsedResult, parse_message

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
        try:
            self._upsert(msg)
        except IntegrityError:
            # A concurrent handler (e.g. a live event racing a backfill replay) inserted the same
            # message first; retrying now takes the "existing message" path.
            log.info("Message %s was stored concurrently; retrying as an update", msg.message_id)
            self._upsert(msg)

    def _upsert(self, msg: ChatMessage) -> None:
        with self.sessions.begin() as session:
            row = self._find(session, msg.platform, msg.channel_id, msg.message_id)
            if row is not None and (row.text, row.user_id, row.thread_id) == (msg.text, msg.user_id, msg.thread_id):
                return  # unchanged replay; reparse covers config changes
            results = parse_message(msg.text, self.games.values())
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

            self._add_results(session, row, results)

    def on_message_deleted(self, platform: str, channel_id: str, message_id: str) -> None:
        with self.sessions.begin() as session:
            row = self._find(session, platform, channel_id, message_id)
            if row is not None:
                session.delete(row)

    def backfill(self, port: ChatPort, *, since: datetime | None = None, default_days: int = 90) -> int:
        """Ingest channel history the bot missed. Returns the number of messages processed.

        Starts from `since` if given; otherwise a day before the latest stored message (to catch
        recent edits), or `default_days` ago for a channel with nothing stored yet.
        """
        total = 0
        for channel in sorted(self.channel_ids):
            oldest = since
            if oldest is None:
                latest = self.latest_posted_at(port.platform, channel)
                oldest = latest - timedelta(days=1) if latest else datetime.now(UTC) - timedelta(days=default_days)
            processed = 0
            for msg in port.fetch_history(channel, oldest):
                self.on_message(msg)
                processed += 1
            log.info("Backfilled %s channel %s since %s: %d messages", port.platform, channel,
                     oldest.isoformat(timespec="seconds"), processed)
            total += processed
        return total

    def latest_posted_at(self, platform: str, channel_id: str) -> datetime | None:
        with self.sessions() as session:
            latest = session.scalar(
                select(func.max(Message.posted_at)).where(
                    Message.platform == platform, Message.channel_id == channel_id
                )
            )
        return from_db(latest) if latest is not None else None

    def reparse(self) -> int:
        """Rebuild every result from the stored messages (e.g. after a game config changed).

        Returns the number of results.
        """
        games = list(self.games.values())
        with self.sessions.begin() as session:
            session.execute(delete(GameResult))  # rounds go via ON DELETE CASCADE
            count = 0
            for row in session.scalars(select(Message).order_by(Message.posted_at, Message.id)).all():
                parsed = parse_message(row.text, games)
                self._add_results(session, row, parsed)
                count += len(parsed)
        log.info("Reparsed stored messages: %d results", count)
        return count

    def _add_results(self, session: Session, row: Message, results: list[ParsedResult]) -> None:
        """Insert results by foreign key (not via `row.results`, which would lazy-load the
        collection once per message during reparse)."""
        if not results:
            return
        if row.id is None:
            session.flush()  # assign the new message's id
        played_on = local_date(row.posted_at, self.tz)
        for parsed in results:
            result = GameResult(message_pk=row.id, game=parsed.game, platform=row.platform,
                                user_id=row.user_id, score=parsed.score, puzzle=parsed.puzzle,
                                played_on=played_on, posted_at=row.posted_at)
            result.rounds = [GameRound(round_no=i, value=v) for i, v in enumerate(parsed.rounds, 1)]
            session.add(result)

    @staticmethod
    def _find(session: Session, platform: str, channel_id: str, message_id: str) -> Message | None:
        return session.scalar(
            select(Message).where(
                Message.platform == platform, Message.channel_id == channel_id, Message.message_id == message_id
            )
        )

    # ── queries ──

    def run_query(self, query: Query) -> BoardResult:
        """Run a board for every requested (or every applicable) game, in games order."""
        board, anchor = query.board, query.anchor
        wanted = set(query.games) if query.games is not None else None
        sections = []
        for game in self.games.values():
            if wanted is not None and game.name not in wanted:
                continue
            if not board_engine.board_applies(board, game):
                continue
            standings = board_engine.run_board(board, game, anchor, partial(self._load_rows, game.name))
            if standings:
                sections.append(board_engine.GameBoardResult(game, standings))
        return board_engine.BoardResult(board, anchor, board_engine.board_range(board, anchor),
                                        board_engine.board_unit(board), sections)

    def _load_rows(self, game: str, date_range: DateRange) -> list[ResultRow]:
        """Every stored result for `game` with played_on in the (inclusive) range."""
        stmt = (
            select(GameResult)
            .where(GameResult.game == game, GameResult.played_on <= date_range.end)
            .options(selectinload(GameResult.rounds))
            .order_by(GameResult.played_on, GameResult.posted_at, GameResult.id)
        )
        if date_range.start is not None:
            stmt = stmt.where(GameResult.played_on >= date_range.start)
        with self.sessions() as session:
            return [
                ResultRow(player=(r.platform, r.user_id), game=r.game, played_on=r.played_on,
                          posted_at=r.posted_at, score=r.score, rounds=tuple(x.value for x in r.rounds))
                for r in session.scalars(stmt)
            ]

    # ── not yet implemented ──

    def on_command(self, text: str) -> str:
        raise NotImplementedError  # T-206

