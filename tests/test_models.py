from __future__ import annotations

from collections.abc import Iterator
from dataclasses import FrozenInstanceError
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from leaderboard.models import Base, GameResult, GameRound, Message
from leaderboard.ports import ChatMessage

POSTED = datetime(2026, 9, 24, 14, 30)  # naive UTC, as stored


@pytest.fixture
def sessions(tmp_path: Path) -> Iterator[sessionmaker[Session]]:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _record) -> None:  # noqa: ANN001
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    yield sessionmaker(engine, expire_on_commit=False)
    engine.dispose()


def make_message(message_id: str = "1727188200.000100", **kw: object) -> Message:
    defaults: dict[str, object] = dict(
        platform="slack", channel_id="C1", message_id=message_id, user_id="U1",
        text="Krillion #72", posted_at=POSTED,
    )
    return Message(**(defaults | kw))


def make_result(**kw: object) -> GameResult:
    defaults: dict[str, object] = dict(
        game="krillion", platform="slack", user_id="U1", score=505.0, puzzle="72",
        played_on=date(2026, 9, 24), posted_at=POSTED,
    )
    return GameResult(**(defaults | kw))


def count(session: Session, model: type[Base]) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def test_create_all_creates_tables(sessions: sessionmaker[Session]) -> None:
    engine = sessions.kw["bind"]
    assert set(inspect(engine).get_table_names()) == {"messages", "game_results", "game_rounds"}


def test_duplicate_message_identity_rejected(sessions: sessionmaker[Session]) -> None:
    with sessions.begin() as s:
        s.add(make_message())
    with pytest.raises(IntegrityError), sessions.begin() as s:
        s.add(make_message())


def test_same_message_id_in_other_channel_allowed(sessions: sessionmaker[Session]) -> None:
    with sessions.begin() as s:
        s.add_all([make_message(), make_message(channel_id="C2")])
    with sessions() as s:
        assert count(s, Message) == 2


def test_one_result_per_game_per_message(sessions: sessionmaker[Session]) -> None:
    with pytest.raises(IntegrityError), sessions.begin() as s:
        msg = make_message()
        msg.results = [make_result(), make_result()]
        s.add(msg)


def test_orm_delete_cascades_to_results_and_rounds(sessions: sessionmaker[Session]) -> None:
    with sessions.begin() as s:
        msg = make_message()
        result = make_result()
        result.rounds = [GameRound(round_no=i, value=v) for i, v in enumerate([85, 100, 30], 1)]
        msg.results = [result]
        s.add(msg)

    with sessions.begin() as s:
        s.delete(s.scalars(select(Message)).one())

    with sessions() as s:
        assert (count(s, Message), count(s, GameResult), count(s, GameRound)) == (0, 0, 0)


def test_database_level_cascade(sessions: sessionmaker[Session]) -> None:
    """Bulk deletes (used by reparse) rely on ON DELETE CASCADE, not the ORM."""
    with sessions.begin() as s:
        msg = make_message()
        result = make_result()
        result.rounds = [GameRound(round_no=1, value=85)]
        msg.results = [result]
        s.add(msg)

    with sessions.begin() as s:
        s.execute(text("DELETE FROM messages"))

    with sessions() as s:
        assert (count(s, GameResult), count(s, GameRound)) == (0, 0)


def test_clearing_results_deletes_orphans(sessions: sessionmaker[Session]) -> None:
    """Re-parsing an edited message replaces its results via `message.results.clear()`."""
    with sessions.begin() as s:
        msg = make_message()
        result = make_result()
        result.rounds = [GameRound(round_no=1, value=85)]
        msg.results = [result]
        s.add(msg)

    with sessions.begin() as s:
        stored = s.scalars(select(Message)).one()  # keep a strong ref: the session's is weak
        stored.results.clear()

    with sessions() as s:
        assert (count(s, Message), count(s, GameResult), count(s, GameRound)) == (1, 0, 0)


def test_rounds_ordered_by_round_no(sessions: sessionmaker[Session]) -> None:
    with sessions.begin() as s:
        msg = make_message()
        result = make_result()
        result.rounds = [GameRound(round_no=n, value=v) for n, v in [(3, 30), (1, 85), (2, 100)]]
        msg.results = [result]
        s.add(msg)

    with sessions() as s:
        rounds = s.scalars(select(GameResult)).one().rounds
        assert [(r.round_no, r.value) for r in rounds] == [(1, 85), (2, 100), (3, 30)]


def test_datetimes_round_trip_as_naive(sessions: sessionmaker[Session]) -> None:
    with sessions.begin() as s:
        s.add(make_message())
    with sessions() as s:
        stored = s.scalars(select(Message)).one().posted_at
        assert stored == POSTED and stored.tzinfo is None


def test_chat_message_is_frozen_with_defaults() -> None:
    msg = ChatMessage("slack", "C1", "1.0", "U1", "hi", datetime(2026, 9, 24, tzinfo=UTC))
    assert msg.thread_id is None
    with pytest.raises(FrozenInstanceError):
        msg.text = "edited"  # type: ignore[misc]
