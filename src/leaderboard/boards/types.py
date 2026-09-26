"""Built-in board types: the whole computation from entries to standings."""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from leaderboard.boards.core import BoardContext, Entry, PlayerKey, Standing, rank
from leaderboard.boards.registry import board_type


def by_player(entries: list[Entry]) -> dict[PlayerKey, list[Entry]]:
    grouped: dict[PlayerKey, list[Entry]] = defaultdict(list)
    for entry in entries:
        grouped[entry.player].append(entry)
    return grouped


@board_type("ranked", description="Aggregate each player's values in the window, then rank")
def ranked(ctx: BoardContext) -> list[Standing]:
    scored = []
    for player, entries in by_player(ctx.entries).items():
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

    wins: dict[PlayerKey, int] = defaultdict(int)
    for day_entries in by_day.values():
        values = [e.value for e in day_entries]
        top = max(values) if ctx.higher_is_better else min(values)
        for entry in day_entries:
            if entry.value == top:
                wins[entry.player] += 1

    scored = []
    for player, entries in by_player(ctx.entries).items():
        days_played = len({e.played_on for e in entries})
        if days_played >= ctx.board.min_entries:
            scored.append((player, float(wins[player]), days_played, f"{days_played} played"))
    return rank(scored, higher_is_better=True)
