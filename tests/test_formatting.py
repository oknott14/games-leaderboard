from __future__ import annotations

from datetime import date

import pytest
from conftest import make_board, sample_games

from leaderboard.boards.core import DateRange, Standing
from leaderboard.boards.engine import BoardResult, GameBoardResult
from leaderboard.commands import CommandError
from leaderboard.formatting import NO_RESULTS, fmt_range, fmt_value, format_board, format_error, format_info


@pytest.mark.parametrize(
    ("value", "unit", "expected"),
    [
        (862.0, None, "862"),
        (38532.0, None, "38,532"),
        (1234567.0, None, "1,234,567"),
        (4.25, None, "4.3"),        # half-up, not banker's rounding
        (4.24, None, "4.2"),
        (86.8, None, "86.8"),
        (72.14285714, None, "72.1"),
        (0.0, None, "0"),
        (-3.0, None, "-3"),
        (1234.56, None, "1,234.6"),
        (120.0, "±", "+120"),
        (-3.5, "±", "-3.5"),
        (0.0, "±", "+0"),
        (5.0, "days", "5 days"),
        (1.0, "days", "1 day"),
        (12.0, "games", "12 games"),
        (1.0, "wins", "1 win"),
        (0.0, "wins", "0 wins"),
        (2.5, "pts", "2.5 pts"),
    ],
)
def test_fmt_value(value: float, unit: str | None, expected: str) -> None:
    assert fmt_value(value, unit) == expected


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        (date(2026, 9, 23), date(2026, 9, 23), "Wed Sep 23"),
        (date(2026, 9, 15), date(2026, 9, 21), "Sep 15–21"),
        (date(2026, 8, 28), date(2026, 9, 3), "Aug 28 – Sep 3"),
        (date(2025, 12, 28), date(2026, 1, 3), "Dec 28, 2025 – Jan 3, 2026"),
        (None, date(2026, 9, 24), "all time to Sep 24"),
    ],
)
def test_fmt_range(start: date | None, end: date, expected: str) -> None:
    assert fmt_range(DateRange(start, end)) == expected


# ── format_board (T-405) ──

GAMES = sample_games()
WEEK = DateRange(date(2026, 9, 15), date(2026, 9, 21))
NAMES = {"U1": "Alice", "U2": "Bob", "U3": "Cara", "U4": "Dan"}


def name_for(platform: str, user_id: str) -> str:
    return NAMES.get(user_id, user_id)


def s(user: str, value: float, rank: int, entries: int = 1, detail: str | None = None) -> Standing:
    return Standing(("slack", user), value, entries, rank, detail)


def board_result(sections: list[tuple[str, list[Standing]]], unit: str | None = None, **board: object) -> BoardResult:
    return BoardResult(make_board(name="weekly", title="Weekly total", **board), date(2026, 9, 21), WEEK, unit,
                       [GameBoardResult(GAMES[g], st) for g, st in sections])


def test_format_board_layout() -> None:
    result = board_result([
        ("maptap", [s("U1", 4321, 1, 5), s("U2", 4100, 2, 5), s("U3", 4100, 2, 4), s("U4", 3900, 4, 5)]),
        ("timeguessr", [s("U2", 38532, 1)]),
    ])
    assert format_board(result, name_for) == (
        "*Weekly total* — Sep 15–21\n"
        "*MapTap*\n"
        "🥇 Alice — 4,321 · 5 games\n"
        "🥈 Bob — 4,100 · 5 games\n"
        "🥈 Cara — 4,100 · 4 games\n"
        "4. Dan — 3,900 · 5 games\n"
        "\n"
        "*TimeGuessr*\n"
        "🥇 Bob — 38,532"
    )


def test_limit_truncates_but_keeps_ranks() -> None:
    standings = [s(f"U{i}", 100 - i, i) for i in range(1, 8)]
    text = format_board(board_result([("maptap", standings)], limit=5), name_for)
    assert "5. U5" in text and "U6" not in text


def test_detail_replaces_the_games_suffix() -> None:
    text = format_board(board_result([("krillion", [s("U1", 2, 1, 3, "3 played")])], unit="wins"), name_for)
    assert "🥇 Alice — 2 wins · 3 played" in text


def test_no_games_suffix_when_the_unit_is_games() -> None:
    text = format_board(board_result([("krillion", [s("U1", 6, 1, 6)])], unit="games"), name_for)
    assert text.endswith("🥇 Alice — 6 games")


def test_improvement_signs() -> None:
    text = format_board(board_result([("maptap", [s("U1", 120, 1, 2, "400 → 520"), s("U2", -30, 2, 2, "90 → 60")])],
                                     unit="±"), name_for)
    assert "🥇 Alice — +120 · 400 → 520" in text and "🥈 Bob — -30 · 90 → 60" in text


def test_title_falls_back_to_board_name() -> None:
    result = BoardResult(make_board(name="adhoc"), date(2026, 9, 24), DateRange(None, date(2026, 9, 24)), None, [])
    assert format_board(result, name_for) == f"*adhoc* — all time to Sep 24\n{NO_RESULTS}"


def test_empty_result() -> None:
    assert format_board(board_result([]), name_for) == f"*Weekly total* — Sep 15–21\n{NO_RESULTS}"


# ── format_info / format_error (T-406) ──


@pytest.fixture(scope="module")
def registries() -> None:
    from leaderboard.boards.registry import load_builtins

    load_builtins()


def test_help() -> None:
    text = format_info("help", GAMES, {})
    assert text.startswith("*Leaderboard commands*")
    assert 6 <= text.count("\n• ") + 1 <= 9 and "`maptap avg month`" in text


def test_games() -> None:
    text = format_info("games", GAMES, {})
    assert "• *MapTap* (`maptap`, `map`): values `score`, `best_round`, `worst_round`, `round_avg`" in text
    assert "• *TimeGuessr* (`timeguessr`, `tg`, `timeguesser`): values `score`" in text
    assert format_info("games", {}, {}) == "*Games*\n_No games configured._"


def test_boards(registries: None) -> None:
    boards = {
        "weekly": make_board(name="weekly", title="Weekly total", window="week", aggregate="sum"),
        "recent_form": make_board(name="recent_form", window={"last_n": 5}, aggregate="avg"),
        "wins": make_board(name="wins", title="Daily wins", type="daily_wins", window="month"),
        "top3": make_board(name="top3", aggregate={"top_k_avg": {"k": 3}}, value="best_round"),
    }
    text = format_info("boards", GAMES, boards)
    assert "• `weekly`: Weekly total (week · sum · score)" in text
    assert "• `recent_form`: recent_form (last_n 5 · avg · score)" in text
    assert "• `wins`: Daily wins (daily_wins · month · score)" in text
    assert "• `top3`: top3 (week · top_k_avg k=3 · best_round)" in text
    assert "*Aggregators*" in text and "• `top_k_avg` (k): Average of the k best values" in text
    assert "*Windows*" in text and "• `last_n` (n):" in text
    assert "*Board types*" in text and "• `improvement`:" in text


def test_boards_lists_plugin_components(registries: None) -> None:
    from leaderboard.boards.registry import AGGREGATORS, aggregator

    try:
        aggregator("t_plugin_agg", description="From a plugin")(lambda e, c: None)
        assert "• `t_plugin_agg`: From a plugin" in format_info("boards", GAMES, {})
    finally:
        AGGREGATORS.pop("t_plugin_agg", None)


def test_boards_when_none_saved(registries: None) -> None:
    assert "_None; build one on the fly" in format_info("boards", GAMES, {})


def test_format_error() -> None:
    assert format_error(CommandError("I didn't understand `wekly`", ["weekly", "week"])) == (
        "I didn't understand `wekly`\nDid you mean: `weekly`, `week`?\nTry `help`."
    )
    assert format_error(CommandError("Two dates")) == "Two dates\nTry `help`."
