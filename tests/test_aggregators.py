from __future__ import annotations

from datetime import date, datetime

import pytest

from leaderboard.boards import aggregators  # noqa: F401  (registers the built-ins)
from leaderboard.boards.core import AggContext, Entry
from leaderboard.boards.registry import AGGREGATORS

ANCHOR = date(2026, 9, 24)


def entry(day: int, value: float, hour: int = 12) -> Entry:
    return Entry(("slack", "U1"), date(2026, 9, day), datetime(2026, 9, day, hour), value)


# Out of chronological order on purpose: latest/first must not rely on input order.
ENTRIES = [entry(22, 30), entry(20, 10), entry(24, 20), entry(21, 40)]


def agg(name: str, entries: list[Entry], *, higher: bool = True, **params: int) -> float | None:
    reg = AGGREGATORS[name]
    parsed = reg.params.model_validate(params) if reg.params else None
    return reg.fn(entries, AggContext(higher, ANCHOR, parsed))


@pytest.mark.parametrize(
    ("name", "expected"),
    [("sum", 100.0), ("avg", 25.0), ("median", 25.0), ("max", 40.0), ("min", 10.0),
     ("latest", 20.0), ("first", 10.0), ("count", 4.0)],
)
def test_values(name: str, expected: float) -> None:
    assert agg(name, ENTRIES) == expected


def test_best_and_worst_follow_direction() -> None:
    assert (agg("best", ENTRIES), agg("worst", ENTRIES)) == (40.0, 10.0)
    assert (agg("best", ENTRIES, higher=False), agg("worst", ENTRIES, higher=False)) == (10.0, 40.0)


def test_max_and_min_ignore_direction() -> None:
    assert (agg("max", ENTRIES, higher=False), agg("min", ENTRIES, higher=False)) == (40.0, 10.0)


def test_latest_breaks_same_day_ties_by_post_time() -> None:
    assert agg("latest", [entry(24, 5, hour=20), entry(24, 9, hour=8)]) == 5.0
    assert agg("first", [entry(24, 5, hour=20), entry(24, 9, hour=8)]) == 9.0


def test_median_of_odd_count() -> None:
    assert agg("median", ENTRIES[:3]) == 20.0


@pytest.mark.parametrize("name", ["sum", "avg", "median", "best", "worst", "max", "min", "latest", "first"])
def test_empty_is_none(name: str) -> None:
    assert agg(name, []) is None


def test_count_of_empty_is_zero() -> None:
    assert agg("count", []) == 0.0


def test_count_metadata() -> None:
    reg = AGGREGATORS["count"]
    assert (reg.unit, reg.higher_is_better) == ("games", True)
    assert AGGREGATORS["sum"].higher_is_better is None


def test_results_are_floats() -> None:
    ints = [entry(20, 3), entry(21, 4)]
    assert all(isinstance(agg(n, ints), float) for n in ("sum", "max", "min", "best", "count", "median"))
