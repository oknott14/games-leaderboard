"""Scheduled auto-posts, driven by the `schedule` section of boards.yaml."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from apscheduler.schedulers.background import BackgroundScheduler

    from leaderboard.boards.config import ScheduleEntry
    from leaderboard.ports import ChatPort
    from leaderboard.service import LeaderboardService


def start_scheduler(
    schedule: list[ScheduleEntry],
    service: LeaderboardService,
    port: ChatPort,
    channel_ids: frozenset[str],
    tz: ZoneInfo,
) -> BackgroundScheduler | None:
    """Start one cron job per schedule entry; `None` if the schedule is empty."""
    raise NotImplementedError  # T-605


def run_schedule_entry(
    entry: ScheduleEntry,
    service: LeaderboardService,
    port: ChatPort,
    channel_ids: frozenset[str],
    today: date,
) -> None:
    raise NotImplementedError  # T-605
