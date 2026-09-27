from __future__ import annotations

from datetime import date

import pytest

from leaderboard.boards.core import DateRange
from leaderboard.formatting import fmt_range, fmt_value


@pytest.mark.parametrize(
    ("value", "unit", "expected"),
    [
        (862.0, None, "862"),
        (38532.0, None, "38,532"),
        (1234567.0, None, "1,234,567"),
        (4.25, None, "4.3"),        # half-up, not banker's rounding
        (4.24, None, "4.2"),
        (86.8, None, "86.8"),
        (72.14285714, None, "72.1"),
        (0.0, None, "0"),
        (-3.0, None, "-3"),
        (1234.56, None, "1,234.6"),
        (120.0, "±", "+120"),
        (-3.5, "±", "-3.5"),
        (0.0, "±", "+0"),
        (5.0, "days", "5 days"),
        (1.0, "days", "1 day"),
        (12.0, "games", "12 games"),
        (1.0, "wins", "1 win"),
        (0.0, "wins", "0 wins"),
        (2.5, "pts", "2.5 pts"),
    ],
)
def test_fmt_value(value: float, unit: str | None, expected: str) -> None:
    assert fmt_value(value, unit) == expected


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        (date(2026, 9, 23), date(2026, 9, 23), "Wed Sep 23"),
        (date(2026, 9, 15), date(2026, 9, 21), "Sep 15–21"),
        (date(2026, 8, 28), date(2026, 9, 3), "Aug 28 – Sep 3"),
        (date(2025, 12, 28), date(2026, 1, 3), "Dec 28, 2025 – Jan 3, 2026"),
        (None, date(2026, 9, 24), "all time to Sep 24"),
    ],
)
def test_fmt_range(start: date | None, end: date, expected: str) -> None:
    assert fmt_range(DateRange(start, end)) == expected
