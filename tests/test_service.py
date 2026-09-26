from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from conftest import SAMPLES, sample_games
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from leaderboard.boards.config import BoardsFile
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
