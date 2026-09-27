from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest
from conftest import SAMPLES, FakePort, sample_games
from sqlalchemy.orm import Session, sessionmaker

from leaderboard.boards.config import BoardsFile, ScheduleEntry
from leaderboard.boards.registry import load_builtins
from leaderboard.ports import ChatMessage
from leaderboard.scheduler import run_schedule_entry, start_scheduler
from leaderboard.service import LeaderboardService

load_builtins()
NY = ZoneInfo("America/New_York")
BOARDS = BoardsFile.model_validate({
    "boards": {
        "daily": {"title": "Daily results", "window": "day", "aggregate": "best"},
        "weekly": {"title": "Weekly total", "window": "week", "aggregate": "sum"},
        "wins": {"title": "Daily wins", "type": "daily_wins", "window": "week"},
    },
})


@pytest.fixture
def service(sessions: sessionmaker[Session]) -> LeaderboardService:
    svc = LeaderboardService(sessions, sample_games(), BOARDS, NY, frozenset({"C1", "C2"}),
                             lambda platform, user: {"U1": "Alice", "U2": "Bob"}.get(user, user))
    # Krillion results in the week of Mon Sep 14 – Sun Sep 20 (last week, as of Thu Sep 24)
    for i, (user, day, text) in enumerate([("U1", 15, SAMPLES["krillion_basic"]),
                                          ("U2", 15, "Krillion #69 🦐\n610\n\n🌟🌟🌟🌟🌟🦑🫧"),
                                          ("U1", 18, SAMPLES["krillion_basic"])]):
        svc.on_message(ChatMessage("slack", "C1", str(i), user, text, datetime(2026, 9, day, 16, tzinfo=UTC)))
    return svc


def entry(boards: list[str], anchor: str = "last_week", cron: str = "0 9 * * MON") -> ScheduleEntry:
    return ScheduleEntry(cron=cron, boards=boards, anchor=anchor)  # type: ignore[arg-type]


def test_posts_one_combined_message_per_channel(service: LeaderboardService) -> None:
    port = FakePort()
    run_schedule_entry(entry(["weekly", "wins"]), service, port, service.channel_ids, date(2026, 9, 24))
    assert [channel for channel, _, _ in port.posted] == ["C1", "C2"]
    (_, text, thread), _ = port.posted
    assert thread is None
    assert text.startswith("*Weekly total* — Sep 14–20\n*Krillion*\n🥇 Alice — 1,010 · 2 games")
    assert "\n\n*Daily wins* — Sep 14–20\n" in text


def test_yesterday_anchor(service: LeaderboardService) -> None:
    port = FakePort()
    run_schedule_entry(entry(["daily"], anchor="yesterday"), service, port, frozenset({"C1"}), date(2026, 9, 19))
    ((_, text, _),) = port.posted
    assert text.startswith("*Daily results* — Fri Sep 18\n*Krillion*\n🥇 Alice — 505")


def test_empty_boards_are_skipped_and_nothing_posted_if_all_empty(service: LeaderboardService,
                                                                   caplog: pytest.LogCaptureFixture) -> None:
    port = FakePort()
    with caplog.at_level(logging.INFO):
        run_schedule_entry(entry(["daily"], anchor="today"), service, port, service.channel_ids, date(2026, 9, 24))
    assert port.posted == []
    assert "no results, nothing posted" in caplog.text


def test_failures_are_logged_not_raised(service: LeaderboardService, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.ERROR):
        run_schedule_entry(entry(["no_such_board"]), service, FakePort(), service.channel_ids, date(2026, 9, 24))
    assert "Scheduled post ['no_such_board'] failed" in caplog.text


def test_start_scheduler_with_an_empty_schedule(service: LeaderboardService) -> None:
    assert start_scheduler([], service, FakePort(), service.channel_ids, NY) is None


def test_start_scheduler_creates_one_job_per_entry(service: LeaderboardService) -> None:
    scheduler = start_scheduler([entry(["daily"], cron="0 9 * * *"), entry(["weekly"])], service, FakePort(),
                                service.channel_ids, NY)
    assert scheduler is not None
    try:
        jobs = scheduler.get_jobs()
        assert [j.name for j in jobs] == ["0 9 * * * daily", "0 9 * * MON weekly"]
        assert all(j.misfire_grace_time == 3600 and j.coalesce for j in jobs)
        next_run = jobs[0].next_run_time
        assert (next_run.hour, next_run.minute, str(next_run.tzinfo)) == (9, 0, "America/New_York")
    finally:
        scheduler.shutdown(wait=False)
