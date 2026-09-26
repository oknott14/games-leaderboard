from __future__ import annotations

from datetime import date, datetime

import pytest
from pydantic import ValidationError

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


# ── T-303: stddev, streak, top_k_avg ──


def test_stddev_is_population_and_lower_is_better() -> None:
    assert agg("stddev", [entry(20, 2), entry(21, 4), entry(22, 4), entry(23, 4),
                          entry(24, 5), entry(19, 5), entry(18, 7), entry(17, 9)]) == 2.0
    assert AGGREGATORS["stddev"].higher_is_better is False


@pytest.mark.parametrize("entries", [[], [entry(24, 5)]])
def test_stddev_needs_two_entries(entries: list[Entry]) -> None:
    assert agg("stddev", entries) is None


@pytest.mark.parametrize(
    ("days", "expected"),
    [
        ([22, 23, 24], 3.0),          # ends on the anchor
        ([21, 22, 23], 3.0),          # ends yesterday: still alive
        ([20, 21, 22], None),         # ended two days ago: broken, dropped from the board
        ([18, 19, 21, 22, 23, 24], 4.0),  # a gap resets it
        ([24, 24, 23], 2.0),          # two results on one day count once
        ([24], 1.0),
        ([], None),
    ],
)
def test_streak(days: list[int], expected: float | None) -> None:
    assert agg("streak", [entry(d, 1) for d in days]) == expected


def test_streak_ignores_days_after_the_anchor() -> None:
    assert agg("streak", [entry(23, 1), entry(24, 1), entry(25, 1)]) == 2.0


def test_streak_across_a_month_boundary() -> None:
    entries = [Entry(("slack", "U1"), date(2026, 8, 31), datetime(2026, 8, 31, 12), 1),
               Entry(("slack", "U1"), date(2026, 9, 1), datetime(2026, 9, 1, 12), 1)]
    reg = AGGREGATORS["streak"]
    assert reg.fn(entries, AggContext(True, date(2026, 9, 1), None)) == 2.0
    assert (reg.unit, reg.higher_is_better) == ("days", True)


def test_top_k_avg_respects_direction_and_k() -> None:
    assert agg("top_k_avg", ENTRIES, k=2) == 35.0            # 40, 30
    assert agg("top_k_avg", ENTRIES, k=2, higher=False) == 15.0  # 10, 20
    assert agg("top_k_avg", ENTRIES, k=10) == 25.0           # fewer than k: all of them
    assert agg("top_k_avg", [], k=3) is None


def test_top_k_avg_rejects_bad_k() -> None:
    with pytest.raises(ValidationError):
        AGGREGATORS["top_k_avg"].params.model_validate({"k": 0})  # type: ignore[union-attr]


def test_top_k_avg_without_params_is_a_clear_error() -> None:
    with pytest.raises(TypeError, match="top_k_avg needs TopKParams"):
        AGGREGATORS["top_k_avg"].fn(ENTRIES, AggContext(True, ANCHOR, None))
