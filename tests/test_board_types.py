from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from typing import Any

from conftest import make_board, sample_games

from leaderboard.boards import types  # noqa: F401  (registers the built-ins)
from leaderboard.boards.core import BoardContext, DateRange, Entry, Standing
from leaderboard.boards.registry import BOARD_TYPES

ANCHOR = date(2026, 9, 24)
GAME = sample_games()["krillion"]
LOWER_GAME = GAME.model_copy(update={"higher_is_better": False})


def entry(player: str, day: int, value: float, hour: int = 12) -> Entry:
    return Entry(("slack", player), date(2026, 9, day), datetime(2026, 9, day, hour), value)


def total(entries: list[Entry]) -> float | None:
    return float(sum(e.value for e in entries))


def context(
    entries: list[Entry],
    *,
    aggregate: Callable[[list[Entry]], float | None] = total,
    higher: bool = True,
    rng: DateRange = DateRange(date(2026, 9, 21), ANCHOR),
    fetch: Callable[[DateRange], list[Entry]] = lambda r: [],
    game: Any = GAME,
    **board: Any,
) -> BoardContext:
    return BoardContext(game=game, board=make_board(**board), value_name="score", higher_is_better=higher,
                        anchor=ANCHOR, range=rng, entries=entries, params=None, aggregate=aggregate, fetch=fetch)


def run(name: str, ctx: BoardContext) -> list[tuple[str, float, int, int, str | None]]:
    standings: list[Standing] = BOARD_TYPES[name].fn(ctx)
    return [(s.player[1], s.value, s.entries, s.rank, s.detail) for s in standings]


# ── ranked ──


def test_ranked_aggregates_per_player_and_ranks() -> None:
    entries = [entry("a", 21, 100), entry("b", 21, 300), entry("a", 22, 250), entry("c", 22, 50)]
    assert run("ranked", context(entries)) == [
        ("a", 350.0, 2, 1, None), ("b", 300.0, 1, 2, None), ("c", 50.0, 1, 3, None),
    ]


def test_ranked_respects_direction() -> None:
    entries = [entry("a", 21, 100), entry("b", 21, 300)]
    assert [p for p, *_ in run("ranked", context(entries, higher=False))] == ["a", "b"]


def test_ranked_applies_min_entries() -> None:
    entries = [entry("a", 21, 100), entry("a", 22, 100), entry("b", 21, 999)]
    assert [p for p, *_ in run("ranked", context(entries, min_entries=2))] == ["a"]


def test_ranked_drops_players_whose_aggregate_is_none() -> None:
    entries = [entry("a", 21, 100), entry("b", 21, 300)]
    only_a = lambda es: None if es[0].player[1] == "b" else total(es)  # noqa: E731
    assert [p for p, *_ in run("ranked", context(entries, aggregate=only_a))] == ["a"]


def test_ranked_ties_share_a_rank() -> None:
    entries = [entry("a", 21, 10), entry("b", 21, 10), entry("c", 21, 5)]
    assert [r for *_, r, _ in run("ranked", context(entries))] == [1, 1, 3]


def test_ranked_empty() -> None:
    assert run("ranked", context([])) == []


# ── daily_wins ──


def test_daily_wins_counts_days_won() -> None:
    entries = [
        entry("a", 21, 500), entry("b", 21, 400),
        entry("a", 22, 300), entry("b", 22, 600),
        entry("a", 23, 700), entry("b", 23, 100), entry("c", 23, 50),
    ]
    assert run("daily_wins", context(entries)) == [
        ("a", 2.0, 3, 1, "3 played"), ("b", 1.0, 3, 2, "3 played"), ("c", 0.0, 1, 3, "1 played"),
    ]


def test_daily_wins_ties_all_win() -> None:
    entries = [entry("a", 21, 500), entry("b", 21, 500), entry("c", 21, 100)]
    assert [(p, v) for p, v, *_ in run("daily_wins", context(entries))] == [("a", 1.0), ("b", 1.0), ("c", 0.0)]


def test_daily_wins_lower_is_better_picks_minimum() -> None:
    entries = [entry("a", 21, 3), entry("b", 21, 5)]
    assert run("daily_wins", context(entries, game=LOWER_GAME))[0][:2] == ("a", 1.0)


def test_daily_wins_min_entries_is_days_played() -> None:
    entries = [entry("a", 21, 9), entry("a", 22, 9), entry("b", 21, 1)]
    assert [p for p, *_ in run("daily_wins", context(entries, min_entries=2))] == ["a"]


def test_daily_wins_ranks_by_wins_even_for_lower_is_better_games() -> None:
    entries = [entry("a", 21, 1), entry("a", 22, 1), entry("b", 21, 9), entry("b", 22, 9)]
    assert [p for p, *_ in run("daily_wins", context(entries, game=LOWER_GAME))] == ["a", "b"]
    assert BOARD_TYPES["daily_wins"].unit == "wins"


# ── code review regressions (round 3) ──


def test_daily_wins_uses_the_values_direction_not_the_boards() -> None:
    entries = [entry("a", 21, 3), entry("b", 21, 5)]
    ctx = context(entries, higher=True, game=LOWER_GAME)  # the board forces higher-is-better ranking
    assert run("daily_wins", ctx)[0][:2] == ("a", 1.0)  # 3 is the day's best score


def test_daily_wins_float_ties_all_win() -> None:
    entries = [entry("a", 21, 0.1 + 0.2), entry("b", 21, 0.3)]
    assert [v for _, v, *_ in run("daily_wins", context(entries))] == [1.0, 1.0]
