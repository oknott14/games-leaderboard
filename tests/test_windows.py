from __future__ import annotations

from datetime import date, datetime

import pytest
from pydantic import ValidationError

from leaderboard.boards import windows  # noqa: F401  (registers the built-ins)
from leaderboard.boards.core import DateRange, Entry, WindowResult
from leaderboard.boards.registry import WINDOWS

THU = date(2026, 9, 24)
SUN = date(2026, 9, 27)
MON = date(2026, 9, 21)


def run(name: str, anchor: date, **params: int) -> WindowResult:
    reg = WINDOWS[name]
    return reg.fn(anchor, reg.params.model_validate(params) if reg.params else None)


def test_all_builtins_registered() -> None:
    assert {"day", "week", "month", "year", "all", "rolling_days", "last_n"} <= set(WINDOWS)
    assert all(WINDOWS[n].description for n in ("day", "week", "last_n"))


@pytest.mark.parametrize(
    ("name", "anchor", "expected"),
    [
        ("day", THU, DateRange(THU, THU)),
        ("week", THU, DateRange(MON, THU)),
        ("week", SUN, DateRange(MON, SUN)),  # anchored on Sunday → the full Mon–Sun week
        ("week", MON, DateRange(MON, MON)),  # anchored on Monday → just that day
        ("month", THU, DateRange(date(2026, 9, 1), THU)),
        ("month", date(2026, 3, 1), DateRange(date(2026, 3, 1), date(2026, 3, 1))),
        ("year", THU, DateRange(date(2026, 1, 1), THU)),
        ("all", THU, DateRange(None, THU)),
    ],
)
def test_calendar_windows(name: str, anchor: date, expected: DateRange) -> None:
    result = run(name, anchor)
    assert result.range == expected and result.select is None


def test_rolling_days_covers_exactly_n_days() -> None:
    rng = run("rolling_days", THU, n=7).range
    assert rng == DateRange(date(2026, 9, 18), THU)
    assert (rng.end - rng.start).days + 1 == 7  # type: ignore[operator]
    assert run("rolling_days", THU, n=1).range == DateRange(THU, THU)


def test_rolling_days_across_a_year_boundary() -> None:
    assert run("rolling_days", date(2026, 1, 3), n=7).range.start == date(2025, 12, 28)


@pytest.mark.parametrize("n", [0, -1])
def test_count_params_must_be_positive(n: int) -> None:
    with pytest.raises(ValidationError):
        WINDOWS["last_n"].params.model_validate({"n": n})  # type: ignore[union-attr]


def entry(player: str, day: int, value: float = 1.0, hour: int = 12) -> Entry:
    return Entry(("slack", player), date(2026, 9, day), datetime(2026, 9, day, hour), value)


def test_last_n_keeps_each_players_latest_independently() -> None:
    result = run("last_n", THU, n=2)
    assert result.range == DateRange(None, THU)
    entries = [entry("a", 20), entry("b", 20), entry("a", 21), entry("a", 22), entry("b", 23), entry("a", 24)]
    assert result.select is not None
    kept = result.select(entries)
    assert [(e.player[1], e.played_on.day) for e in kept] == [("b", 20), ("a", 22), ("b", 23), ("a", 24)]


def test_last_n_breaks_same_day_ties_by_post_time() -> None:
    select = run("last_n", THU, n=1).select
    assert select is not None
    early, late = entry("a", 24, 1.0, hour=8), entry("a", 24, 2.0, hour=20)
    assert select([late, early]) == [late]


def test_last_n_with_fewer_entries_keeps_all() -> None:
    select = run("last_n", THU, n=5).select
    assert select is not None
    entries = [entry("a", 20), entry("a", 21)]
    assert select(entries) == entries
