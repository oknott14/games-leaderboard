from __future__ import annotations

from datetime import date

import pytest
from conftest import make_board, make_rows, sample_games

from leaderboard.boards.core import DateRange, ResultRow
from leaderboard.boards.engine import board_applies, board_range, board_unit, run_board
from leaderboard.boards.registry import load_builtins
from leaderboard.config import GameConfig

load_builtins()

GAMES = sample_games()
ANCHOR = date(2026, 9, 24)  # Thursday


def loader(rows: list[ResultRow], calls: list[DateRange] | None = None):  # noqa: ANN201
    def load(rng: DateRange) -> list[ResultRow]:
        if calls is not None:
            calls.append(rng)
        return [r for r in rows if (rng.start is None or r.played_on >= rng.start) and r.played_on <= rng.end]
    return load


def standings(board_kw: dict, rows: list[ResultRow], game: str | GameConfig = "krillion") -> list[tuple[str, float, int]]:
    config = GAMES[game] if isinstance(game, str) else game
    result = run_board(make_board(**board_kw), config, ANCHOR, loader(rows))
    return [(s.player[1], s.value, s.rank) for s in result]


K = (85, 100, 30, 85, 85, 60, 60)  # 505
ROWS = make_rows([
    ("alice", "2026-09-21", 505, K, "09:00"),
    ("alice", "2026-09-21", 700, (100,) * 7, "20:00"),  # second post the same day
    ("bob", "2026-09-22", 610, (100, 100, 100, 100, 100, 60, 50), "10:00"),
    ("alice", "2026-09-23", 400, (60,) * 5 + (50, 50), "10:00"),
    ("carol", "2026-09-18", 999, (100,) * 7, "10:00"),  # last week
], game="krillion")


def test_weekly_sum_with_first_post_policy() -> None:
    assert standings({"window": "week", "aggregate": "sum"}, ROWS) == [("alice", 905.0, 1), ("bob", 610.0, 2)]


def test_best_duplicate_policy_changes_the_counted_post() -> None:
    best_policy = GAMES["krillion"].model_copy(update={"duplicates": "best"})
    assert standings({"window": "week", "aggregate": "sum"}, ROWS, best_policy)[0] == ("alice", 1100.0, 1)


def test_round_value_comes_from_the_post_dedupe_kept() -> None:
    # first-post policy keeps the 09:00 post, so the best round is 90, not the later post's 100
    rows = make_rows([("alice", "2026-09-21", 505, (85, 90), "09:00"), ("alice", "2026-09-21", 700, (100,), "20:00")],
                     game="krillion")
    assert standings({"value": "best_round", "window": "week", "aggregate": "best"}, rows) == [("alice", 90.0, 1)]


def test_window_all_and_last_n() -> None:
    assert standings({"window": "all", "aggregate": "best"}, ROWS)[0] == ("carol", 999.0, 1)
    last_one = standings({"window": {"last_n": 1}, "aggregate": "sum"}, ROWS)
    assert dict((p, v) for p, v, _ in last_one) == {"alice": 400.0, "bob": 610.0, "carol": 999.0}


def test_direction_precedence_board_over_aggregator_over_value() -> None:
    rows = make_rows([("a", "2026-09-22", 1, K), ("a", "2026-09-23", 9, K), ("b", "2026-09-22", 5, K),
                      ("b", "2026-09-23", 5, K)], game="krillion")
    # stddev forces lower-is-better: b (0 spread) beats a
    assert standings({"aggregate": "stddev"}, rows)[0][0] == "b"
    # a board override beats the aggregator's forced direction
    assert standings({"aggregate": "stddev", "higher_is_better": True}, rows)[0][0] == "a"
    # no override anywhere: the value's direction (higher is better)
    assert standings({"aggregate": "sum"}, rows)[0][0] == "a"


def test_rows_with_no_value_are_skipped() -> None:
    rows = make_rows([("a", "2026-09-22", 505), ("b", "2026-09-22", 505, K)], game="krillion")  # a has no rounds
    assert [p for p, *_ in standings({"value": "best_round", "aggregate": "best"}, rows)] == ["b"]


def test_all_standings_are_returned_untruncated() -> None:
    rows = make_rows([(f"p{i}", "2026-09-22", i) for i in range(15)], game="timeguessr")
    assert len(standings({"limit": 3}, rows, game="timeguessr")) == 15


def test_improvement_fetches_the_previous_period_through_the_same_pipeline() -> None:
    calls: list[DateRange] = []
    rows = make_rows([("a", "2026-09-15", 400, (), "09:00"), ("a", "2026-09-15", 999, (), "20:00"),
                      ("a", "2026-09-22", 600)], game="timeguessr")
    board = make_board(type="improvement", window="week", aggregate="avg")
    (standing,) = run_board(board, GAMES["timeguessr"], date(2026, 9, 27), loader(rows, calls))
    assert (standing.value, standing.detail) == (200.0, "400 → 600")  # dedupe applied to the prior week too
    assert calls == [DateRange(date(2026, 9, 21), date(2026, 9, 27)), DateRange(date(2026, 9, 14), date(2026, 9, 20))]


def test_board_applies() -> None:
    assert board_applies(make_board(), GAMES["timeguessr"])
    assert not board_applies(make_board(value="best_round"), GAMES["timeguessr"])  # no rounds
    assert board_applies(make_board(value="best_round"), GAMES["krillion"])
    assert not board_applies(make_board(games=["maptap"]), GAMES["krillion"])


def test_board_range_and_unit() -> None:
    assert board_range(make_board(window="week"), ANCHOR) == DateRange(date(2026, 9, 21), ANCHOR)
    assert board_range(make_board(window={"rolling_days": 3}), ANCHOR).start == date(2026, 9, 22)
    assert board_unit(make_board(aggregate="streak")) == "days"
    assert board_unit(make_board(type="daily_wins", aggregate="streak")) == "wins"  # board type wins
    assert board_unit(make_board()) is None


@pytest.mark.parametrize(
    ("kw", "match"),
    [({"window": "fortnight"}, "unknown window 'fortnight'"),
     ({"aggregate": "mode"}, "unknown aggregator 'mode'"),
     ({"type": "podium"}, "unknown board type 'podium'"),
     ({"window": {"last_n": 0}}, "last_n: invalid parameters")],
)
def test_bad_components_are_clear_errors(kw: dict, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        run_board(make_board(**kw), GAMES["krillion"], ANCHOR, loader([]))
