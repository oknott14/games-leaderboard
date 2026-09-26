from __future__ import annotations

import pytest
from conftest import make_rows

from leaderboard.boards.core import Standing, dedupe_daily, rank


def picked(rows, policy: str, higher: bool = True) -> list[tuple[str, int, float]]:  # noqa: ANN001
    return [(r.player[1], r.played_on.day, r.score) for r in dedupe_daily(rows, policy, higher)]  # type: ignore[arg-type]


# alice posts three times on the 24th, deliberately out of order
ROWS = make_rows([
    ("alice", "2026-09-24", 700, (), "18:00"),
    ("alice", "2026-09-24", 500, (), "08:00"),
    ("alice", "2026-09-24", 900, (), "12:00"),
    ("bob", "2026-09-24", 600, (), "09:00"),
    ("alice", "2026-09-23", 400, (), "10:00"),
])


def test_first_keeps_the_earliest_post() -> None:
    assert picked(ROWS, "first") == [("alice", 23, 400.0), ("alice", 24, 500.0), ("bob", 24, 600.0)]


def test_last_keeps_the_latest_post() -> None:
    assert ("alice", 24, 700.0) in picked(ROWS, "last")


def test_best_follows_direction() -> None:
    assert ("alice", 24, 900.0) in picked(ROWS, "best", higher=True)
    assert ("alice", 24, 500.0) in picked(ROWS, "best", higher=False)


def test_best_tie_goes_to_the_earliest_post() -> None:
    rows = make_rows([("a", "2026-09-24", 5, (1,), "20:00"), ("a", "2026-09-24", 5, (2,), "07:00")])
    (kept,) = dedupe_daily(rows, "best", True)
    assert kept.rounds == (2.0,)


def test_output_is_chronological() -> None:
    rows = dedupe_daily(ROWS, "first", True)
    assert [(r.played_on, r.posted_at) for r in rows] == sorted((r.played_on, r.posted_at) for r in rows)


def test_players_on_other_platforms_are_distinct() -> None:
    rows = make_rows([("a", "2026-09-24", 1)]) + make_rows([("a", "2026-09-24", 2)], platform="discord")
    assert len(dedupe_daily(rows, "first", True)) == 2


def test_dedupe_empty() -> None:
    assert dedupe_daily([], "first", True) == []


# ── rank ──

A, B, C, D = (("slack", u) for u in "abcd")


def ranks(standings: list[Standing]) -> list[tuple[str, float, int]]:
    return [(s.player[1], s.value, s.rank) for s in standings]


def test_competition_ranking_higher_is_better() -> None:
    scored = [(C, 90.0, 1, None), (A, 100.0, 1, None), (D, 80.0, 1, None), (B, 90.0, 1, None)]
    assert ranks(rank(scored, True)) == [("a", 100.0, 1), ("b", 90.0, 2), ("c", 90.0, 2), ("d", 80.0, 4)]


def test_lower_is_better() -> None:
    scored = [(A, 3.0, 1, None), (B, 1.0, 1, None), (C, 3.0, 1, None)]
    assert ranks(rank(scored, False)) == [("b", 1.0, 1), ("a", 3.0, 2), ("c", 3.0, 2)]


def test_all_tied() -> None:
    assert [s.rank for s in rank([(B, 5.0, 1, None), (A, 5.0, 1, None)], True)] == [1, 1]


def test_entries_and_detail_carried_through() -> None:
    (standing,) = rank([(A, 5.0, 3, "+2 vs last week")], True)
    assert (standing.entries, standing.detail) == (3, "+2 vs last week")


@pytest.mark.parametrize("higher", [True, False])
def test_rank_empty(higher: bool) -> None:
    assert rank([], higher) == []
