"""Leaderboard engine. This module is the public plugin API.

    from leaderboard.boards import aggregator, AggContext, Entry

See docs/plan/03-boards-engine.md.
"""

from leaderboard.boards.core import AggContext, BoardContext, DateRange, Entry, Standing, WindowResult
from leaderboard.boards.registry import aggregator, board_type, window

__all__ = [
    "AggContext",
    "BoardContext",
    "DateRange",
    "Entry",
    "Standing",
    "WindowResult",
    "aggregator",
    "board_type",
    "window",
]
