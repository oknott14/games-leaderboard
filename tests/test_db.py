from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from sqlalchemy import func, select, text

from leaderboard.db import make_session_factory
from leaderboard.models import GameResult, GameRound, Message


def pragma(sessions, name: str):  # noqa: ANN001, ANN201
    with sessions() as s:
        return s.execute(text(f"PRAGMA {name}")).scalar()


def test_creates_missing_directory_and_tables(tmp_path: Path) -> None:
    db = tmp_path / "nested" / "dir" / "leaderboard.db"
    sessions = make_session_factory(f"sqlite:///{db}")
    assert db.parent.is_dir()
    with sessions() as s:
        assert s.scalar(select(func.count()).select_from(Message)) == 0
    assert db.exists()


def test_pragmas(tmp_path: Path) -> None:
    sessions = make_session_factory(f"sqlite:///{tmp_path / 'x.db'}")
    assert pragma(sessions, "foreign_keys") == 1
    assert pragma(sessions, "journal_mode") == "wal"
    assert pragma(sessions, "busy_timeout") == 5000


def test_raw_delete_cascades(tmp_path: Path) -> None:
    sessions = make_session_factory(f"sqlite:///{tmp_path / 'x.db'}")
    with sessions.begin() as s:
        msg = Message(platform="slack", channel_id="C1", message_id="1", user_id="U1",
                      text="t", posted_at=datetime(2026, 9, 24, 12))
        result = GameResult(game="krillion", platform="slack", user_id="U1", score=505,
                            played_on=date(2026, 9, 24), posted_at=datetime(2026, 9, 24, 12))
        result.rounds = [GameRound(round_no=1, value=85)]
        msg.results = [result]
        s.add(msg)
    with sessions.begin() as s:
        s.execute(text("DELETE FROM messages"))
    with sessions() as s:
        assert s.scalar(select(func.count()).select_from(GameRound)) == 0


def test_idempotent_on_existing_database(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'x.db'}"
    make_session_factory(url)
    sessions = make_session_factory(url)  # create_all again is a no-op
    assert pragma(sessions, "foreign_keys") == 1


def test_in_memory_database() -> None:
    sessions = make_session_factory("sqlite://")
    assert pragma(sessions, "foreign_keys") == 1
