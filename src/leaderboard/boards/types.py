"""Built-in board types: the whole computation from entries to standings."""

from __future__ import annotations

from collections import defaultdict

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
