"""Standard 5-field crontab → APScheduler trigger.

APScheduler 3's `CronTrigger.from_crontab` numbers weekdays from 0 = Monday, but crontab (and
everyone writing boards.yaml) uses 0 = Sunday, so `0 9 * * 1` would fire on Tuesdays. Numeric
day-of-week values are translated to names first; names (`MON`, `mon-fri`) already agree.
"""

from __future__ import annotations

from zoneinfo import ZoneInfo

from apscheduler.triggers.cron import CronTrigger

_DAYS = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"]


def cron_trigger(expression: str, tz: ZoneInfo | None = None) -> CronTrigger:
    """A trigger for a standard crontab (0 or 7 = Sunday). Raises ValueError if invalid."""
    fields = expression.split()
    if len(fields) != 5:
        raise ValueError(f"expected 5 fields (minute hour day month weekday), got {len(fields)}")
    minute, hour, day, month, weekday = fields
    return CronTrigger(minute=minute, hour=hour, day=day, month=month,
                       day_of_week=_weekday_names(weekday), timezone=tz)


def _weekday_names(field: str) -> str:
    """`1` → `mon`, `1-5` → `mon,tue,wed,thu,fri`, `0,6` → `sun,sat`, `*/2` → `sun,tue,thu,sat`.
    Fields without digits (`*`, `MON`, `mon-fri`) are passed through unchanged."""
    if not any(ch.isdigit() for ch in field):
        return field
    days: list[str] = []
    for part in field.split(","):
        spec, _, step_text = part.partition("/")
        step = int(step_text) if step_text else 1
        if spec == "*":
            start, end = 0, 6
        elif "-" in spec:
            low, high = spec.split("-", 1)
            start, end = _day_number(low), _day_number(high)
        else:
            start = end = _day_number(spec)
        if end < start:
            raise ValueError(f"weekday range {spec!r} runs backwards")
        for number in range(start, end + 1, step):
            name = _DAYS[number % 7]
            if name not in days:
                days.append(name)
    return ",".join(days)


def _day_number(token: str) -> int:
    if token.isdecimal():
        number = int(token)
        if not 0 <= number <= 7:
            raise ValueError(f"weekday {number} is out of range (0-7, 0 and 7 = Sunday)")
        return number
    if token.lower()[:3] in _DAYS:
        return _DAYS.index(token.lower()[:3])
    raise ValueError(f"unknown weekday {token!r}")
