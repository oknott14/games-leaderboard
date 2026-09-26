from __future__ import annotations

from datetime import date

import pytest

from leaderboard.commands import resolve_anchor

THU = date(2026, 9, 24)


@pytest.mark.parametrize(
    ("token", "today", "expected"),
    [
        ("today", THU, THU),
        ("TODAY", THU, THU),
        ("yesterday", THU, date(2026, 9, 23)),
        ("yesterday", date(2026, 1, 1), date(2025, 12, 31)),
        ("lastweek", THU, date(2026, 9, 20)),         # the previous Sunday
        ("last_week", THU, date(2026, 9, 20)),
        ("lastweek", date(2026, 9, 21), date(2026, 9, 20)),  # on a Monday
        ("lastweek", date(2026, 9, 27), date(2026, 9, 20)),  # on a Sunday: the week before, not today
        ("lastweek", date(2026, 1, 2), date(2025, 12, 28)),  # across a year boundary
        ("lastmonth", THU, date(2026, 8, 31)),
        ("last_month", date(2026, 3, 15), date(2026, 2, 28)),
        ("lastmonth", date(2026, 1, 10), date(2025, 12, 31)),
        ("2026-09-01", THU, date(2026, 9, 1)),
    ],
)
def test_resolve_anchor(token: str, today: date, expected: date) -> None:
    assert resolve_anchor(token, today) == expected


@pytest.mark.parametrize("token", ["weekly", "2026-13-01", "2026-9-1", "20260901", "tomorrow", ""])
def test_not_an_anchor(token: str) -> None:
    assert resolve_anchor(token, THU) is None
