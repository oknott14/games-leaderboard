"""Built-in board types: the whole computation from entries to standings."""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from leaderboard.boards.core import BoardContext, Entry, PlayerKey, Standing, group_by_player, rank, same_value
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
