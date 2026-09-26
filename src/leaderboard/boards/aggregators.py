"""Built-in aggregators: combine one player's values in the window into one number.

Each receives the player's entries (sorted by played_on) and an `AggContext` whose
`higher_is_better` is the *value's* direction. Returning `None` drops the player from the board.
"""

from __future__ import annotations

import statistics

from leaderboard.boards.core import AggContext, Entry
from leaderboard.boards.registry import aggregator


def _values(entries: list[Entry]) -> list[float]:
    return [e.value for e in entries]


def _chronological(entries: list[Entry]) -> list[Entry]:
    return sorted(entries, key=lambda e: (e.played_on, e.posted_at))


@aggregator("sum", description="Total of all values")
def sum_(entries: list[Entry], ctx: AggContext) -> float | None:
    return float(sum(_values(entries))) if entries else None


@aggregator("avg", description="Mean value")
def avg(entries: list[Entry], ctx: AggContext) -> float | None:
    return statistics.fmean(_values(entries)) if entries else None


@aggregator("median", description="Median value")
def median(entries: list[Entry], ctx: AggContext) -> float | None:
    return float(statistics.median(_values(entries))) if entries else None


@aggregator("best", description="Best single value (respects the game's direction)")
def best(entries: list[Entry], ctx: AggContext) -> float | None:
    if not entries:
        return None
    return float(max(_values(entries)) if ctx.higher_is_better else min(_values(entries)))


@aggregator("worst", description="Worst single value (respects the game's direction)")
def worst(entries: list[Entry], ctx: AggContext) -> float | None:
    if not entries:
        return None
    return float(min(_values(entries)) if ctx.higher_is_better else max(_values(entries)))


@aggregator("max", description="Highest value")
def max_(entries: list[Entry], ctx: AggContext) -> float | None:
    return float(max(_values(entries))) if entries else None


@aggregator("min", description="Lowest value")
def min_(entries: list[Entry], ctx: AggContext) -> float | None:
    return float(min(_values(entries))) if entries else None


@aggregator("latest", description="Most recent value")
def latest(entries: list[Entry], ctx: AggContext) -> float | None:
    return _chronological(entries)[-1].value if entries else None


@aggregator("first", description="Earliest value")
def first(entries: list[Entry], ctx: AggContext) -> float | None:
    return _chronological(entries)[0].value if entries else None


@aggregator("count", description="Number of results", unit="games", higher_is_better=True)
def count(entries: list[Entry], ctx: AggContext) -> float | None:
    return float(len(entries))
