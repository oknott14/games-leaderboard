from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from conftest import SAMPLES, FakePort, make_board, sample_games
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from leaderboard.boards import engine
from leaderboard.boards.config import BoardsFile
from leaderboard.boards.core import DateRange, Standing
from leaderboard.commands import Query
from leaderboard.models import GameResult, GameRound, Message
from leaderboard.ports import ChatMessage
from leaderboard.service import LeaderboardService, from_db, local_date, to_db

NY = ZoneInfo("America/New_York")
T0 = datetime(2026, 9, 24, 16, 0, tzinfo=UTC)  # 12:00 in New York


def make_service(sessions: sessionmaker[Session], **kw: object) -> LeaderboardService:
    defaults: dict[str, object] = dict(
        games=sample_games(), boards=BoardsFile(), tz=NY, channel_ids=frozenset({"C1"}),
        name_for=lambda platform, user: user, today=lambda: date(2026, 9, 24),
    )
    return LeaderboardService(sessions, **(defaults | kw))  # type: ignore[arg-type]


def msg(text: str, message_id: str = "1", *, user: str = "U1", channel: str = "C1",
        at: datetime = T0, thread: str | None = None) -> ChatMessage:
    return ChatMessage("slack", channel, message_id, user, text, at, thread)


def count(sessions: sessionmaker[Session], model: type) -> int:
    with sessions() as s:
        return s.scalar(select(func.count()).select_from(model)) or 0


def results(sessions: sessionmaker[Session]) -> list[GameResult]:
    with sessions() as s:
        rows = s.scalars(select(GameResult).order_by(GameResult.id)).all()
        for r in rows:
            _ = r.rounds  # load while the session is open
        return list(rows)


@pytest.fixture
def service(sessions: sessionmaker[Session]) -> LeaderboardService:
    return make_service(sessions)


# ── time helpers ──


def test_time_helpers_round_trip() -> None:
    naive = to_db(datetime(2026, 9, 24, 12, 0, tzinfo=NY))
    assert naive == datetime(2026, 9, 24, 16, 0) and naive.tzinfo is None
    assert from_db(naive) == datetime(2026, 9, 24, 16, 0, tzinfo=UTC)


def test_local_date_uses_local_midnight() -> None:
    # 03:30 UTC on the 25th is 23:30 on the 24th in New York
    assert local_date(datetime(2026, 9, 25, 3, 30, tzinfo=UTC), NY) == date(2026, 9, 24)
    assert local_date(datetime(2026, 9, 25, 3, 30), NY) == date(2026, 9, 24)  # stored naive UTC


# ── ingest ──


def test_new_game_message_stores_message_results_and_rounds(service, sessions) -> None:  # noqa: ANN001
    service.on_message(msg(SAMPLES["krillion_basic"]))
    (result,) = results(sessions)
    assert (result.game, result.user_id, result.score, result.puzzle) == ("krillion", "U1", 505.0, "72")
    assert result.played_on == date(2026, 9, 24)
    assert [r.value for r in result.rounds] == [85, 100, 30, 85, 85, 60, 60]
    assert [r.round_no for r in result.rounds] == [1, 2, 3, 4, 5, 6, 7]
    with sessions() as s:
        stored = s.scalars(select(Message)).one()
        assert stored.posted_at == datetime(2026, 9, 24, 16, 0) and stored.edited_at is None


def test_multi_game_message(service, sessions) -> None:  # noqa: ANN001
    service.on_message(msg(SAMPLES["two_games_one_message"]))
    assert sorted(r.game for r in results(sessions)) == ["krillion", "timeguessr"]


def test_local_day_boundary(service, sessions) -> None:  # noqa: ANN001
    late = datetime(2026, 9, 25, 3, 30, tzinfo=UTC)  # 23:30 on the 24th in New York
    early = datetime(2026, 9, 25, 4, 30, tzinfo=UTC)  # 00:30 on the 25th in New York
    service.on_message(msg(SAMPLES["krillion_basic"], "1", at=late))
    service.on_message(msg(SAMPLES["krillion_basic"], "2", at=early))
    assert [r.played_on for r in results(sessions)] == [date(2026, 9, 24), date(2026, 9, 25)]


def test_edit_replaces_results_and_sets_edited_at(service, sessions) -> None:  # noqa: ANN001
    service.on_message(msg(SAMPLES["krillion_basic"]))
    service.on_message(msg("Krillion #72 🦐\n610\n\n🌟🌟🌟🌟🌟🦑🫧"))
    (result,) = results(sessions)
    assert result.score == 610.0 and [r.value for r in result.rounds] == [100] * 5 + [60, 10]
    assert count(sessions, GameRound) == 7
    with sessions() as s:
        assert s.scalars(select(Message)).one().edited_at is not None


def test_edit_removing_game_text_removes_results(service, sessions) -> None:  # noqa: ANN001
    service.on_message(msg(SAMPLES["krillion_basic"]))
    service.on_message(msg("oops wrong channel"))
    assert (count(sessions, Message), count(sessions, GameResult), count(sessions, GameRound)) == (1, 0, 0)


def test_replay_is_idempotent(service, sessions) -> None:  # noqa: ANN001
    for _ in range(3):
        service.on_message(msg(SAMPLES["krillion_basic"]))
    assert (count(sessions, Message), count(sessions, GameResult), count(sessions, GameRound)) == (1, 1, 7)
    with sessions() as s:
        assert s.scalars(select(Message)).one().edited_at is None  # same text isn't an edit


def test_delete_removes_message_results_and_rounds(service, sessions) -> None:  # noqa: ANN001
    service.on_message(msg(SAMPLES["krillion_basic"]))
    service.on_message_deleted("slack", "C1", "1")
    assert (count(sessions, Message), count(sessions, GameResult), count(sessions, GameRound)) == (0, 0, 0)


def test_delete_of_unknown_message_is_a_no_op(service) -> None:  # noqa: ANN001
    service.on_message_deleted("slack", "C1", "nope")


def test_other_channel_is_ignored(service, sessions) -> None:  # noqa: ANN001
    service.on_message(msg(SAMPLES["krillion_basic"], channel="C2"))
    assert count(sessions, Message) == 0


def test_non_game_messages_stored_by_default(service, sessions) -> None:  # noqa: ANN001
    service.on_message(msg(SAMPLES["not_a_game"], thread="0.9"))
    assert (count(sessions, Message), count(sessions, GameResult)) == (1, 0)


def test_store_non_game_false(sessions) -> None:  # noqa: ANN001
    service = make_service(sessions, store_non_game=False)
    service.on_message(msg(SAMPLES["not_a_game"], "1"))
    service.on_message(msg(SAMPLES["krillion_basic"], "2"))
    assert (count(sessions, Message), count(sessions, GameResult)) == (1, 1)
    service.on_message(msg("never mind", "2"))  # edited into a non-game message
    assert (count(sessions, Message), count(sessions, GameResult)) == (0, 0)


def test_results_copy_message_identity(service, sessions) -> None:  # noqa: ANN001
    service.on_message(msg(SAMPLES["krillion_basic"], user="U7", at=T0 + timedelta(hours=1)))
    (result,) = results(sessions)
    assert (result.platform, result.user_id, result.posted_at) == ("slack", "U7", datetime(2026, 9, 24, 17, 0))


def test_today_defaults_to_now_in_tz(sessions) -> None:  # noqa: ANN001
    service = make_service(sessions, today=None)
    assert service.today() == datetime.now(NY).date()


# ── reparse (T-203) ──


def test_reparse_applies_changed_game_config(sessions) -> None:  # noqa: ANN001
    service = make_service(sessions)
    service.on_message(msg(SAMPLES["krillion_basic"], "1"))
    service.on_message(msg(SAMPLES["timeguessr_basic"], "2"))
    service.on_message(msg(SAMPLES["not_a_game"], "3"))

    # a new config reads Krillion's puzzle number as the score (deliberately different)
    games = sample_games()
    games["krillion"] = games["krillion"].model_copy(update={
        "score": games["krillion"].score.model_copy(update={"pattern": r"Krillion #(?P<value>\d+)"}),  # type: ignore[union-attr]
        "rounds": None, "values": {},
    })
    changed = make_service(sessions, games=games)
    assert changed.reparse() == 2
    by_game = {r.game: r for r in results(sessions)}
    assert by_game["krillion"].score == 72.0 and by_game["krillion"].rounds == []
    assert by_game["timeguessr"].score == 38532.0


def test_reparse_picks_up_newly_added_games(sessions) -> None:  # noqa: ANN001
    games = sample_games()
    only_tg = make_service(sessions, games={"timeguessr": games["timeguessr"]})
    only_tg.on_message(msg(SAMPLES["krillion_basic"], "1"))  # stored, but Krillion isn't configured yet
    assert results(sessions) == []
    assert make_service(sessions).reparse() == 1
    assert [r.game for r in results(sessions)] == ["krillion"]


def test_reparse_is_stable(service, sessions) -> None:  # noqa: ANN001
    service.on_message(msg(SAMPLES["two_games_one_message"], "1"))
    service.on_message(msg(SAMPLES["krillion_basic"], "2"))
    first = service.reparse()
    second = service.reparse()
    assert first == second == 3
    assert (count(sessions, GameResult), count(sessions, GameRound)) == (3, 14)


def test_reparse_keeps_local_played_on(service, sessions) -> None:  # noqa: ANN001
    service.on_message(msg(SAMPLES["krillion_basic"], at=datetime(2026, 9, 25, 3, 30, tzinfo=UTC)))
    service.reparse()
    assert results(sessions)[0].played_on == date(2026, 9, 24)


def test_reparse_empty_database(service) -> None:  # noqa: ANN001
    assert service.reparse() == 0


# ── backfill (T-204) ──


class SpyPort(FakePort):
    def __init__(self, **kw: object) -> None:
        super().__init__(**kw)  # type: ignore[arg-type]
        self.requests: list[tuple[str, datetime]] = []

    def fetch_history(self, channel_id: str, oldest: datetime):  # noqa: ANN201
        self.requests.append((channel_id, oldest))
        return super().fetch_history(channel_id, oldest)


def history(n: int, *, channel: str = "C1", start: datetime = T0) -> list[ChatMessage]:
    return [msg(SAMPLES["krillion_basic"] if i % 2 == 0 else SAMPLES["not_a_game"], f"{channel}-{i}",
                channel=channel, at=start + timedelta(hours=i)) for i in range(n)]


def test_latest_posted_at(service) -> None:  # noqa: ANN001
    assert service.latest_posted_at("slack", "C1") is None
    service.on_message(msg("a", "1", at=T0))
    service.on_message(msg("b", "2", at=T0 + timedelta(hours=3)))
    latest = service.latest_posted_at("slack", "C1")
    assert latest == T0 + timedelta(hours=3) and latest.tzinfo is UTC
    assert service.latest_posted_at("slack", "C9") is None


def test_backfill_ingests_history(service, sessions) -> None:  # noqa: ANN001
    port = SpyPort(history=history(4))
    assert service.backfill(port, since=T0 - timedelta(days=1)) == 4
    assert (count(sessions, Message), count(sessions, GameResult)) == (4, 2)


def test_backfill_explicit_since(service) -> None:  # noqa: ANN001
    port = SpyPort()
    service.backfill(port, since=T0)
    assert port.requests == [("C1", T0)]


def test_backfill_first_run_uses_default_days(service) -> None:  # noqa: ANN001
    port = SpyPort()
    before = datetime.now(UTC)
    service.backfill(port, default_days=30)
    ((_, oldest),) = port.requests
    assert before - timedelta(days=30, seconds=5) <= oldest <= datetime.now(UTC) - timedelta(days=30)


def test_backfill_resumes_a_day_before_latest(service) -> None:  # noqa: ANN001
    service.on_message(msg("seen", "1", at=T0))
    port = SpyPort()
    service.backfill(port)
    assert port.requests == [("C1", T0 - timedelta(days=1))]


def test_backfill_every_channel_independently(sessions) -> None:  # noqa: ANN001
    service = make_service(sessions, channel_ids=frozenset({"C1", "C2"}))
    service.on_message(msg("seen", "1", channel="C1", at=T0))
    port = SpyPort(history=history(2, channel="C2"))
    assert service.backfill(port) == 2
    (c1, c2) = port.requests
    assert c1 == ("C1", T0 - timedelta(days=1)) and c2[0] == "C2"


def test_backfill_replay_is_idempotent(service, sessions) -> None:  # noqa: ANN001
    port = SpyPort(history=history(6))
    service.backfill(port, since=T0 - timedelta(days=1))
    service.backfill(port, since=T0 - timedelta(days=1))
    assert (count(sessions, Message), count(sessions, GameResult), count(sessions, GameRound)) == (6, 3, 21)


# ── run_query (T-205), with the engine stubbed until T-315 ──


@pytest.fixture
def fake_engine(monkeypatch: pytest.MonkeyPatch) -> dict[str, list]:
    """Engine stand-in: every game applies except TimeGuessr for `top_round`; run_board returns one
    standing per loaded row and records the ranges it was asked to load."""
    calls: dict[str, list] = {"loaded": []}

    def run_board(board, game, anchor, load_rows):  # noqa: ANN001, ANN202
        rows = load_rows(DateRange(date(2026, 9, 21), anchor))
        calls["loaded"].append((game.name, rows))
        return [Standing(r.player, r.score, 1, i) for i, r in enumerate(rows, 1)]

    monkeypatch.setattr(engine, "run_board", run_board)
    monkeypatch.setattr(engine, "board_applies", lambda b, g: not (b.name == "top_round" and g.name == "timeguessr"))
    monkeypatch.setattr(engine, "board_range", lambda b, a: DateRange(date(2026, 9, 21), a))
    monkeypatch.setattr(engine, "board_unit", lambda b: "days")
    return calls


def seed(service: LeaderboardService) -> None:
    for i, (text, day) in enumerate([
        (SAMPLES["krillion_basic"], 20), (SAMPLES["krillion_basic"], 22),  # 20th is before the range
        (SAMPLES["timeguessr_basic"], 23), (SAMPLES["krillion_slack"], 24),
    ]):
        service.on_message(msg(text, str(i), at=datetime(2026, 9, day, 16, tzinfo=UTC)))


def test_run_query_loads_rows_in_range_per_game(service, fake_engine) -> None:  # noqa: ANN001
    seed(service)
    result = service.run_query(Query(make_board(name="weekly"), None, date(2026, 9, 24)))
    assert [s.game.name for s in result.sections] == ["timeguessr", "krillion"]  # games order; maptap empty
    loaded = dict(fake_engine["loaded"])
    assert [r.played_on for r in loaded["krillion"]] == [date(2026, 9, 22), date(2026, 9, 24)]
    assert loaded["krillion"][0].rounds == (85.0, 100.0, 30.0, 85.0, 85.0, 60.0, 60.0)
    assert loaded["maptap"] == []
    assert (result.anchor, result.range.start, result.unit) == (date(2026, 9, 24), date(2026, 9, 21), "days")


def test_run_query_game_filter(service, fake_engine) -> None:  # noqa: ANN001
    seed(service)
    result = service.run_query(Query(make_board(), ["krillion"], date(2026, 9, 24)))
    assert [s.game.name for s in result.sections] == ["krillion"]
    assert [g for g, _ in fake_engine["loaded"]] == ["krillion"]


def test_run_query_skips_games_the_board_doesnt_apply_to(service, fake_engine) -> None:  # noqa: ANN001
    seed(service)
    service.run_query(Query(make_board(name="top_round"), None, date(2026, 9, 24)))
    assert "timeguessr" not in [g for g, _ in fake_engine["loaded"]]


def test_load_rows_unbounded_start(service) -> None:  # noqa: ANN001
    seed(service)
    rows = service._load_rows("krillion", DateRange(None, date(2026, 9, 24)))
    assert [r.played_on.day for r in rows] == [20, 22, 24]
    assert rows[0].player == ("slack", "U1") and rows[0].posted_at.tzinfo is None


# ── code review regressions (round 2) ──


def test_unchanged_replay_does_not_rewrite_results(service, sessions) -> None:  # noqa: ANN001
    service.on_message(msg(SAMPLES["krillion_basic"]))
    before = [r.id for r in results(sessions)]
    service.on_message(msg(SAMPLES["krillion_basic"]))
    assert [r.id for r in results(sessions)] == before


def test_concurrent_insert_retries_as_update(service, sessions, monkeypatch) -> None:  # noqa: ANN001
    service.on_message(msg(SAMPLES["krillion_basic"]))  # "the other thread" already stored it
    real_find = LeaderboardService._find
    misses = iter([True])

    def racing_find(session, *key):  # noqa: ANN001, ANN202
        return None if next(misses, False) else real_find(session, *key)

    monkeypatch.setattr(LeaderboardService, "_find", staticmethod(racing_find))
    service.on_message(msg("Krillion #72 🦐\n610\n\n🌟🌟🌟🌟🌟🦑🫧"))
    assert [r.score for r in results(sessions)] == [610.0]


def test_reparse_query_count_is_constant(service, sessions) -> None:  # noqa: ANN001
    from sqlalchemy import event

    for i in range(20):
        service.on_message(msg(SAMPLES["krillion_basic"], str(i), at=T0 + timedelta(minutes=i)))
    selects: list[str] = []
    engine = sessions.kw["bind"]
    listener = lambda *a: selects.append(a[2]) if a[2].lstrip().upper().startswith("SELECT") else None  # noqa: E731
    event.listen(engine, "before_cursor_execute", listener)
    try:
        service.reparse()
    finally:
        event.remove(engine, "before_cursor_execute", listener)
    assert len(selects) <= 2  # the messages query, not one per message


# ── on_command (T-206), with commands/formatting stubbed until T-402/T-405/T-406 ──


@pytest.fixture
def fake_commands(monkeypatch: pytest.MonkeyPatch, fake_engine) -> dict[str, object]:  # noqa: ANN001
    from leaderboard import commands, formatting

    seen: dict[str, object] = {}

    def parse_command(text, *, today, games, boards):  # noqa: ANN001, ANN202
        seen["parse"] = (text, today, sorted(games), boards)
        if text == "help":
            return commands.InfoRequest("help")
        if text == "boom":
            raise RuntimeError("kaboom")
        if text.startswith("weekly"):
            return commands.Query(make_board(name="weekly"), None, today)
        return commands.CommandError("didn't understand", ["weekly"])

    monkeypatch.setattr(commands, "parse_command", parse_command)
    monkeypatch.setattr(formatting, "format_board",
                        lambda result, name_for: f"board:{result.board.name}:{[s.game.name for s in result.sections]}"
                        f":{name_for('slack', 'U1')}")
    monkeypatch.setattr(formatting, "format_info", lambda topic, games, boards: f"info:{topic}")
    monkeypatch.setattr(formatting, "format_error", lambda err: f"error:{err.message}:{err.suggestions}")
    return seen


def test_on_command_query_runs_the_board(sessions, fake_commands) -> None:  # noqa: ANN001
    service = make_service(sessions, name_for=lambda platform, user: f"@{user}")
    service.on_message(msg(SAMPLES["krillion_basic"]))
    assert service.on_command("weekly") == "board:weekly:['krillion']:@U1"
    assert fake_commands["parse"] == ("weekly", date(2026, 9, 24), ["krillion", "maptap", "timeguessr"], {})


def test_on_command_info(service, fake_commands) -> None:  # noqa: ANN001
    assert service.on_command("help") == "info:help"


def test_on_command_error(service, fake_commands) -> None:  # noqa: ANN001
    assert service.on_command("wekly") == "error:didn't understand:['weekly']"


def test_on_command_exception_gives_fallback(service, fake_commands, caplog) -> None:  # noqa: ANN001
    from leaderboard.service import COMMAND_FAILED

    with caplog.at_level(logging.ERROR):
        assert service.on_command("boom") == COMMAND_FAILED
    assert "Command 'boom' failed" in caplog.text and "RuntimeError: kaboom" in caplog.text


def test_on_command_passes_saved_boards(sessions, fake_commands) -> None:  # noqa: ANN001
    boards = BoardsFile.model_validate({"boards": {"weekly": {"window": "week"}}})
    make_service(sessions, boards=boards).on_command("help")
    assert list(fake_commands["parse"][3]) == ["weekly"]  # type: ignore[index]
