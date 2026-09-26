"""Engine and session setup."""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker


def make_session_factory(url: str) -> sessionmaker[Session]:
    """Create the engine (with SQLite pragmas), create tables, and return a session factory."""
    raise NotImplementedError  # T-201
