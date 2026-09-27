"""Scheduled auto-posts, driven by the `schedule` section of boards.yaml."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date, datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from leaderboard.commands import Query, resolve_anchor
from leaderboard.formatting import format_board

if TYPE_CHECKING:
    from leaderboard.boards.config import ScheduleEntry
    from leaderboard.ports import ChatPort
    from leaderboard.service import LeaderboardService

log = logging.getLogger(__name__)


def start_scheduler(
    schedule: list[ScheduleEntry],
    service: LeaderboardService,
    port: ChatPort,
    channel_ids: frozenset[str],
    tz: ZoneInfo,
) -> BackgroundScheduler | None:
    """Start one cron job per schedule entry; `None` if the schedule is empty.

    Runs missed while the machine was asleep are posted only if it wakes within an hour
    (`misfire_grace_time`), and several missed runs of a job collapse into one (`coalesce`).
    """
    if not schedule:
        return None
    scheduler = BackgroundScheduler(timezone=tz)
    for i, entry in enumerate(schedule):
        scheduler.add_job(
            _job(entry, service, port, channel_ids, tz),
            CronTrigger.from_crontab(entry.cron, timezone=tz),
            id=f"schedule-{i}",
            name=f"{entry.cron} {', '.join(entry.boards)}",
            misfire_grace_time=3600,
            coalesce=True,
        )
    scheduler.start()
    for job in scheduler.get_jobs():
        log.info("Scheduled %s; next run %s", job.name, job.next_run_time)
    return scheduler


def _job(entry: ScheduleEntry, service: LeaderboardService, port: ChatPort,
         channel_ids: frozenset[str], tz: ZoneInfo) -> Callable[[], None]:
    def run() -> None:
        run_schedule_entry(entry, service, port, channel_ids, datetime.now(tz).date())
    return run


def run_schedule_entry(
    entry: ScheduleEntry,
    service: LeaderboardService,
    port: ChatPort,
    channel_ids: frozenset[str],
    today: date,
) -> None:
    """Post the entry's boards, as one message, to every channel. Boards with no results are
    skipped; if all are empty nothing is posted. Never raises (the scheduler must keep running)."""
    try:
        anchor = resolve_anchor(entry.anchor, today)
        if anchor is None:
            raise ValueError(f"unknown anchor {entry.anchor!r}")
        blocks = []
        for name in entry.boards:
            result = service.run_query(Query(service.boards.boards[name], None, anchor))
            if result.sections:
                blocks.append(format_board(result, service.name_for))
        if not blocks:
            log.info("Scheduled post %s for %s: no results, nothing posted", entry.boards, anchor)
            return
        text = "\n\n".join(blocks)
        for channel in sorted(channel_ids):
            port.post(channel, text)
        log.info("Posted %s for %s to %d channel(s)", entry.boards, anchor, len(channel_ids))
    except Exception:
        log.exception("Scheduled post %s failed", entry.boards)
