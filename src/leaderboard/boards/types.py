"""Built-in board types: the whole computation from entries to standings."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from leaderboard.boards.core import (
    BoardContext,
    DateRange,
    Entry,
    PlayerKey,
    Standing,
    group_by_player,
    rank,
    same_value,
)
from leaderboard.boards.registry import board_type


@board_type("ranked", description="Aggregate each player's values in the window, then rank")
def ranked(ctx: BoardContext) -> list[Standing]:
    scored = []
    for player, entries in group_by_player(ctx.entries).items():
        if len(entries) < ctx.board.min_entries:
            continue
        value = ctx.aggregate(entries)
        if value is not None:
            scored.append((player, value, len(entries), None))
    return rank(scored, ctx.higher_is_better)


@board_type("daily_wins", description="Days each player had the day's best value (ties all win)", unit="wins")
def daily_wins(ctx: BoardContext) -> list[Standing]:
    by_day: dict[date, list[Entry]] = defaultdict(list)
    for entry in ctx.entries:
        by_day[entry.played_on].append(entry)

    # The day's best is judged by the *value's* direction, not the board's ranking direction
    # (a board may rank higher-is-better while the game's scores are lower-is-better).
    value_higher = ctx.game.higher_is_better_for(ctx.value_name)
    wins: dict[PlayerKey, int] = defaultdict(int)
    for day_entries in by_day.values():
        values = [e.value for e in day_entries]
        top = max(values) if value_higher else min(values)
        for entry in day_entries:
            if same_value(entry.value, top):
                wins[entry.player] += 1

    scored = []
    for player, entries in group_by_player(ctx.entries).items():
        days_played = len(entries)  # entries are deduped to one per player per day
        if days_played >= ctx.board.min_entries:
            scored.append((player, float(wins[player]), days_played, f"{days_played} played"))
    return rank(scored, higher_is_better=True)


@board_type("improvement", description="Change in each player's aggregate vs the previous period (+ = better)",
            unit="±")
def improvement(ctx: BoardContext) -> list[Standing]:
    """Compare the window with the same-length period immediately before it.

    Only players with enough results in both periods are ranked. The delta is signed so that a
    positive number always means improved, in the aggregate's direction.
    """
    if ctx.range.start is None:
        raise ValueError("improvement needs a bounded window (not `all` or `last_n`)")
    length = ctx.range.end - ctx.range.start + timedelta(days=1)
    previous = DateRange(ctx.range.start - length, ctx.range.start - timedelta(days=1))

    now = group_by_player(ctx.entries)
    before = group_by_player(ctx.fetch(previous))
    sign = 1 if ctx.higher_is_better else -1
    scored = []
    for player, entries in now.items():
        prior = before.get(player, [])
        if min(len(entries), len(prior)) < ctx.board.min_entries:
            continue
        current, past = ctx.aggregate(entries), ctx.aggregate(prior)
        if current is None or past is None:
            continue
        scored.append((player, sign * (current - past), len(entries), f"{_num(past)} → {_num(current)}"))
    return rank(scored, higher_is_better=True)


def _num(value: float) -> str:
    return f"{value:,.0f}" if float(value).is_integer() else f"{value:,.1f}"
