from __future__ import annotations

import importlib
import pkgutil
import re
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
import yaml
from sqlalchemy import inspect
from sqlalchemy.orm import Session, sessionmaker

import leaderboard
from leaderboard.boards.core import AggContext, DateRange, Entry, Standing, WindowResult
from leaderboard.boards.engine import BoardResult, GameBoardResult
from leaderboard.commands import CommandError, InfoRequest, Query
from leaderboard.config import GameConfig
from leaderboard.parser import ParsedResult
from leaderboard.ports import ChatMessage
from leaderboard.settings import Settings
from conftest import SAMPLES, FakePort, make_board, make_rows, sample_games

PARSING_DOC = Path(__file__).parents[1] / "docs" / "plan" / "01-parsing.md"
MODULES = sorted(
    m.name for m in pkgutil.walk_packages(leaderboard.__path__, "leaderboard.") if m.name != "leaderboard.__main__"
)


@pytest.mark.parametrize("module", MODULES)
def test_every_module_imports(module: str) -> None:
    importlib.import_module(module)


def test_only_the_adapter_may_import_slack() -> None:
    src = Path(leaderboard.__file__).parent
    offenders = [
        p.relative_to(src).as_posix()
        for p in src.rglob("*.py")
        if p.parent.name != "adapters" and re.search(r"^\s*(from|import)\s+slack", p.read_text(), re.M)
    ]
    assert offenders == []


def test_contract_dataclasses_construct(fixed_today: date) -> None:
    board = make_board()
    games = sample_games()
    rng = DateRange(None, fixed_today)
    assert ChatMessage("slack", "C1", "1.0", "U1", "hi", datetime(2026, 9, 24, tzinfo=UTC)).thread_id is None
    assert ParsedResult("krillion", 505).rounds == ()
    assert Entry(("slack", "U1"), fixed_today, datetime(2026, 9, 24), 1.0).value == 1.0
    standing = Standing(("slack", "U1"), 1.0, 1, 1)
    assert WindowResult(rng).select is None
    assert AggContext(True, fixed_today, None).params is None
    result = BoardResult(board, fixed_today, rng, None, [GameBoardResult(games["maptap"], [standing])])
    assert result.sections[0].standings == [standing]
    assert Query(board, None, fixed_today).games is None
    assert InfoRequest("help").topic == "help"
    assert CommandError("nope").suggestions == []
    settings = Settings("xoxb", "xapp", frozenset({"C1"}), timezone=ZoneInfo("UTC"))
    assert settings.database_url == "sqlite:///data/leaderboard.db"


# ── fixtures ──


def test_fixed_today_is_a_thursday(fixed_today: date) -> None:
    assert fixed_today == date(2026, 9, 24) and fixed_today.strftime("%A") == "Thursday"


def test_samples_cover_the_contract_keys() -> None:
    assert set(SAMPLES) >= {
        "maptap_basic", "maptap_slack_raw", "timeguessr_basic", "krillion_basic",
        "krillion_slack", "two_games_one_message", "not_a_game",
    }


def test_sample_games_match_the_parsing_doc() -> None:
    """The in-code games must equal the examples in 01-parsing.md §5.6."""
    blocks = re.findall(r"```yaml\n(# games/(\w+)\.yaml.*?)```", PARSING_DOC.read_text(), re.S)
    from_doc = {name: GameConfig.model_validate(yaml.safe_load(body) | {"name": name}) for body, name in blocks}
    assert sample_games() == from_doc


def test_sample_games_are_fresh_copies() -> None:
    a, b = sample_games(), sample_games()
    a["maptap"].aliases.append("x")
    assert "x" not in b["maptap"].aliases


def test_make_rows() -> None:
    alice, bob = make_rows([("alice", "2026-09-22", 862), ("bob", "2026-09-22", 900, (90, 95), "08:15")])
    assert alice.player == ("slack", "alice") and alice.rounds == () and alice.posted_at.hour == 12
    assert bob.rounds == (90.0, 95.0) and bob.posted_at == datetime(2026, 9, 22, 8, 15)
    assert make_rows([("c", "2026-09-22", 1)], game="krillion")[0].game == "krillion"


def test_make_board_accepts_shorthand() -> None:
    board = make_board(window={"last_n": 5}, aggregate="avg")
    assert (board.name, board.window.name, board.aggregate.name) == ("test", "last_n", "avg")


def test_fake_port(fixed_today: date) -> None:
    t0 = datetime(2026, 9, 24, 12, tzinfo=UTC)
    port = FakePort(names={"U1": "Alice"})
    port.history = [
        ChatMessage("slack", "C1", "1", "U1", "old", t0 - timedelta(days=2)),
        ChatMessage("slack", "C1", "2", "U1", "new", t0),
        ChatMessage("slack", "C2", "3", "U1", "other channel", t0),
    ]
    assert [m.text for m in port.fetch_history("C1", t0 - timedelta(days=1))] == ["new"]
    port.post("C1", "hi", thread_id="2")
    assert port.posted == [("C1", "hi", "2")]
    assert (port.display_name("U1"), port.display_name("U9")) == ("Alice", "U9")
    port.run(handler=None)  # type: ignore[arg-type]  # no-op


def test_sessions_fixture(sessions: sessionmaker[Session]) -> None:
    assert set(inspect(sessions.kw["bind"]).get_table_names()) == {"messages", "game_results", "game_rounds"}
    with sessions() as s:
        assert s.connection().exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
