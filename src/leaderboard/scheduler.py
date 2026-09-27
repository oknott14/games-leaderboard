"""Scheduled auto-posts, driven by the `schedule` section of boards.yaml."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from leaderboard.crontab import cron_trigger

from leaderboard.commands import Query, resolve_anchor
from leaderboard.formatting import format_board

if TYPE_CHECKING:
    from leaderboard.boards.config import ScheduleEntry
    from leaderboard.ports import ChatPort
    from leaderboard.service import LeaderboardService

log = logging.getLogger(__name__)

MISFIRE_GRACE_SECONDS = 3600  # a run missed while asleep still happens if the machine wakes within this


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
        trigger = cron_trigger(entry.cron, tz)
        scheduler.add_job(
            _job(entry, trigger, service, port, channel_ids, tz),
            trigger,
            id=f"schedule-{i}",
            name=f"{entry.cron} {', '.join(entry.boards)}",
            misfire_grace_time=MISFIRE_GRACE_SECONDS,
            coalesce=True,
        )
    scheduler.start()
    for job in scheduler.get_jobs():
        log.info("Scheduled %s; next run %s", job.name, job.next_run_time)
    return scheduler


def _job(entry: ScheduleEntry, trigger: CronTrigger, service: LeaderboardService, port: ChatPort,
         channel_ids: frozenset[str], tz: ZoneInfo) -> Callable[[], None]:
    def run() -> None:
        run_schedule_entry(entry, service, port, channel_ids, scheduled_date(trigger, datetime.now(tz)))
    return run


def scheduled_date(trigger: CronTrigger, now: datetime) -> date:
    """The date the run was *scheduled* for. A run delayed past midnight (the machine was
    asleep) must use its intended day, not the wake-up day."""
    earliest = now - timedelta(seconds=MISFIRE_GRACE_SECONDS + 1)
    scheduled = trigger.get_next_fire_time(None, earliest)
    return (scheduled if scheduled is not None and scheduled <= now else now).date()


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
    except Exception:
        log.exception("Scheduled post %s failed", entry.boards)
        return
    for channel in sorted(channel_ids):
        try:  # one unreachable channel mustn't stop the others
            port.post(channel, text)
            log.info("Posted %s for %s to %s", entry.boards, anchor, channel)
        except Exception:
            log.exception("Scheduled post %s to %s failed", entry.boards, channel)
