"""SQLAlchemy ORM models.

All `datetime` columns hold **naive UTC** (SQLite has no timezone support); convert at the service
boundary. `GameResult.played_on` is the message's date in the configured local timezone.

Derived data (duplicate resolution, leaderboards) is never stored: it is computed at query time,
and results can always be rebuilt from `messages` by re-parsing.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("platform", "channel_id", "message_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    platform: Mapped[str] = mapped_column(String(32))
    channel_id: Mapped[str] = mapped_column(String(64))
    message_id: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    text: Mapped[str] = mapped_column(Text)
    posted_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    thread_id: Mapped[str | None] = mapped_column(String(64))
    edited_at: Mapped[datetime | None] = mapped_column(DateTime)

    results: Mapped[list[GameResult]] = relationship(
        back_populates="message", cascade="all, delete-orphan", passive_deletes=True
    )


class GameResult(Base):
    __tablename__ = "game_results"
    __table_args__ = (UniqueConstraint("message_pk", "game"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    message_pk: Mapped[int] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"))
    game: Mapped[str] = mapped_column(String(64), index=True)
    platform: Mapped[str] = mapped_column(String(32))
    user_id: Mapped[str] = mapped_column(String(64))
    score: Mapped[float] = mapped_column(Float)
    puzzle: Mapped[str | None] = mapped_column(String(64))
    played_on: Mapped[date] = mapped_column(Date, index=True)
    posted_at: Mapped[datetime] = mapped_column(DateTime)

    message: Mapped[Message] = relationship(back_populates="results")
    rounds: Mapped[list[GameRound]] = relationship(
        back_populates="result",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="GameRound.round_no",
    )


class GameRound(Base):
    __tablename__ = "game_rounds"

    result_pk: Mapped[int] = mapped_column(
        ForeignKey("game_results.id", ondelete="CASCADE"), primary_key=True
    )
    round_no: Mapped[int] = mapped_column(primary_key=True)  # 1-based
    value: Mapped[float] = mapped_column(Float)

    result: Mapped[GameResult] = relationship(back_populates="rounds")
