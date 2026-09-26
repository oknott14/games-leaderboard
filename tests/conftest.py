"""Shared test fakes and fixtures. These are part of the contract (docs/plan/00-contracts.md §6)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from leaderboard.boards.config import BoardConfig
from leaderboard.boards.core import ResultRow
from leaderboard.config import GameConfig
from leaderboard.models import Base
from leaderboard.ports import ChatHandler, ChatMessage

FIXED_TODAY = date(2026, 9, 24)  # a Thursday

# Share texts as they arrive from the adapter (already normalised, emoji as Slack sends them).
# MapTap and TimeGuessr are best guesses until T-107 replaces them with real samples.
SAMPLES: dict[str, str] = {
    "maptap_basic": "www.maptap.gg September 24\n93:trophy: 88:fire: 71 97:trophy: 85\nFinal score: 862",
    "maptap_slack_raw": (
        "<http://www.maptap.gg|www.maptap.gg> September 24\n"
        "93:trophy: 88:fire: 71 97:trophy: 85\nFinal score: 862"
    ),
    "timeguessr_basic": (
        "TimeGuessr #512 38,532/50,000\n"
        ":earth_africa::large_green_square::large_green_square::black_large_square: "
        ":calendar::large_green_square::large_yellow_square::black_large_square:"
    ),
    "krillion_basic": "Krillion #72 🦐\n505\n\n🏮🌟🐟🏮🏮🦑🦑",  # real sample
    "krillion_slack": (
        "Krillion #72 :shrimp:\n505\n\n"
        ":izakaya_lantern::star2::fish::izakaya_lantern::izakaya_lantern::squid::squid:"
    ),
    "two_games_one_message": (
        "today's haul\nTimeGuessr #512 38,532/50,000\n\nKrillion #72 🦐\n505\n\n🏮🌟🐟🏮🏮🦑🦑"
    ),
    "not_a_game": "anyone want lunch? I scored 505 on my step count lol",
}

_ROUND_VALUES = {"best_round": {"from_rounds": "max"}, "worst_round": {"from_rounds": "min"},
                 "round_avg": {"from_rounds": "avg"}}

_KRILLION_TILES = {"🫧": 10, ":bubbles:": 10, "🐟": 30, ":fish:": 30, "🦑": 60, ":squid:": 60,
                   "🏮": 85, ":izakaya_lantern:": 85, ":lantern:": 85, "🌟": 100, ":star2:": 100}

# Keep in sync with docs/plan/01-parsing.md §5.6 (and games/*.yaml once T-107 lands).
_GAMES: dict[str, dict[str, Any]] = {
    "maptap": {
        "display_name": "MapTap",
        "aliases": ["map"],
        "flags": ["IGNORECASE"],
        "detect": r"maptap\.gg",
        "score": {"pattern": r"final score:?\s*(?P<value>[\d,]+)"},
        "rounds": {"block": r"maptap\.gg[^\n]*\n(?P<block>[^\n]+)", "item": r"(\d+)"},
        "values": _ROUND_VALUES,
    },
    "timeguessr": {
        "display_name": "TimeGuessr",
        "aliases": ["tg", "timeguesser"],
        "detect": r"TimeGuessr\s+#\d+",
        "score": {"pattern": r"TimeGuessr\s+#\d+\s+(?P<value>[\d,]+)\s*/\s*50,000"},
        "puzzle": {"pattern": r"TimeGuessr\s+#(?P<value>\d+)"},
    },
    "krillion": {
        "display_name": "Krillion",
        "aliases": ["krill"],
        "flags": ["IGNORECASE", "MULTILINE"],
        "detect": r"Krillion\s+#\d+",
        "score": {"pattern": r"Krillion\s+#\d+[^\n]*\n\s*(?P<value>[\d,]+)\s*$"},
        "puzzle": {"pattern": r"Krillion\s+#(?P<value>\d+)"},
        "rounds": {
            "block": r"Krillion\s+#\d+[^\n]*\n\s*[\d,]+[ \t]*\n\s*(?P<block>[^\n]+)",
            "item": r":(?:bubbles|fish|squid|izakaya_lantern|lantern|star2):|🫧|🐟|🦑|🏮|🌟",
            "map": _KRILLION_TILES,
            "check_sum": True,
        },
        "values": _ROUND_VALUES,
    },
}


def sample_games() -> dict[str, GameConfig]:
    """MapTap, TimeGuessr and Krillion, built in code. Fresh objects on every call."""
    return {name: GameConfig.model_validate({"name": name} | raw) for name, raw in _GAMES.items()}


RowSpec = tuple[Any, ...]  # (user, "YYYY-MM-DD", score[, rounds[, "HH:MM" posted time]])


def make_rows(spec: list[RowSpec], *, game: str = "maptap", platform: str = "slack") -> list[ResultRow]:
    """Compact `ResultRow` builder.

    make_rows([("alice", "2026-09-22", 862), ("bob", "2026-09-22", 900, (90, 95), "08:15")])
    Posted time defaults to 12:00 (naive UTC) on the played date.
    """
    rows = []
    for user, day, score, *rest in spec:
        rounds = tuple(rest[0]) if rest else ()
        played_on = date.fromisoformat(day)
        posted = time.fromisoformat(rest[1]) if len(rest) > 1 else time(12, 0)
        rows.append(ResultRow(player=(platform, user), game=game, played_on=played_on,
                              posted_at=datetime.combine(played_on, posted), score=float(score),
                              rounds=tuple(float(r) for r in rounds)))
    return rows


def make_board(**kw: Any) -> BoardConfig:
    """`BoardConfig` with defaults; accepts YAML shorthand, e.g. make_board(window={"last_n": 5})."""
    return BoardConfig.model_validate({"name": "test"} | kw)


@dataclass
class FakePort:
    """In-memory `ChatPort`."""

    platform: str = "slack"
    history: list[ChatMessage] = field(default_factory=list)
    posted: list[tuple[str, str, str | None]] = field(default_factory=list)  # (channel, text, thread)
    names: dict[str, str] = field(default_factory=dict)
    handler: ChatHandler | None = None

    def fetch_history(self, channel_id: str, oldest: datetime) -> Iterator[ChatMessage]:
        for msg in self.history:
            if msg.channel_id == channel_id and msg.posted_at >= oldest:
                yield msg

    def post(self, channel_id: str, text: str, thread_id: str | None = None) -> None:
        self.posted.append((channel_id, text, thread_id))

    def display_name(self, user_id: str) -> str:
        return self.names.get(user_id, user_id)

    def run(self, handler: ChatHandler) -> None:
        self.handler = handler  # no event loop; tests call handler methods directly


@pytest.fixture
def fixed_today() -> date:
    return FIXED_TODAY


@pytest.fixture
def fake_port() -> FakePort:
    return FakePort()


@pytest.fixture
def sessions(tmp_path: Path) -> Iterator[sessionmaker[Session]]:
    """Session factory over a temporary SQLite file. Independent of db.py."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _record) -> None:  # noqa: ANN001
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    yield sessionmaker(engine, expire_on_commit=False)
    engine.dispose()
