from __future__ import annotations

from datetime import date

import pytest
from conftest import make_board, sample_games

from leaderboard.commands import CommandError, InfoRequest, Query, parse_command, resolve_anchor

THU = date(2026, 9, 24)


@pytest.mark.parametrize(
    ("token", "today", "expected"),
    [
        ("today", THU, THU),
        ("TODAY", THU, THU),
        ("yesterday", THU, date(2026, 9, 23)),
        ("yesterday", date(2026, 1, 1), date(2025, 12, 31)),
        ("lastweek", THU, date(2026, 9, 20)),         # the previous Sunday
        ("last_week", THU, date(2026, 9, 20)),
        ("lastweek", date(2026, 9, 21), date(2026, 9, 20)),  # on a Monday
        ("lastweek", date(2026, 9, 27), date(2026, 9, 20)),  # on a Sunday: the week before, not today
        ("lastweek", date(2026, 1, 2), date(2025, 12, 28)),  # across a year boundary
        ("lastmonth", THU, date(2026, 8, 31)),
        ("last_month", date(2026, 3, 15), date(2026, 2, 28)),
        ("lastmonth", date(2026, 1, 10), date(2025, 12, 31)),
        ("2026-09-01", THU, date(2026, 9, 1)),
    ],
)
def test_resolve_anchor(token: str, today: date, expected: date) -> None:
    assert resolve_anchor(token, today) == expected


@pytest.mark.parametrize("token", ["weekly", "2026-13-01", "2026-9-1", "20260901", "tomorrow", ""])
def test_not_an_anchor(token: str) -> None:
    assert resolve_anchor(token, THU) is None


# ── parse_command: saved boards, anchors, games, shortcuts (T-402) ──

BOARDS = {name: make_board(name=name) for name in ("daily", "weekly", "average", "wins")}
GAMES = sample_games()


def parse(text: str, boards: dict | None = None) -> Query | InfoRequest | CommandError:
    return parse_command(text, today=THU, games=GAMES, boards=BOARDS if boards is None else boards)


def query(text: str) -> tuple[str, list[str] | None, date]:
    result = parse(text)
    assert isinstance(result, Query), result
    return result.board.name, result.games, result.anchor


@pytest.mark.parametrize("text", ["", "   ", "help", "HELP"])
def test_help(text: str) -> None:
    assert parse(text) == InfoRequest("help")


@pytest.mark.parametrize("topic", ["games", "boards"])
def test_info_topics(topic: str) -> None:
    assert parse(topic) == InfoRequest(topic)  # type: ignore[arg-type]


def test_reserved_word_must_be_alone() -> None:
    assert isinstance(parse("help maptap"), CommandError)
    assert isinstance(parse("maptap games"), CommandError)


def test_saved_board_defaults() -> None:
    assert query("weekly") == ("weekly", None, THU)


def test_any_order_gives_the_same_query() -> None:
    expected = ("weekly", ["maptap"], date(2026, 9, 20))
    assert query("maptap weekly lastweek") == query("lastweek weekly maptap") == query("Weekly MapTap LASTWEEK") == expected


def test_alias_and_display_name_resolve_to_the_game_id() -> None:
    assert query("daily 2026-09-01 tg") == ("daily", ["timeguessr"], date(2026, 9, 1))
    assert query("weekly timeguessr krill") == ("weekly", ["timeguessr", "krillion"], THU)
    assert query("weekly map maptap")[1] == ["maptap"]  # repeated game counted once


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("lastweek", ("weekly", None, date(2026, 9, 20))),
        ("lastmonth", ("average", None, date(2026, 8, 31))),
        ("yesterday", ("daily", None, date(2026, 9, 23))),
        ("today maptap", ("daily", ["maptap"], THU)),
        ("maptap", ("daily", ["maptap"], THU)),
        ("2026-09-01", ("daily", None, date(2026, 9, 1))),
    ],
)
def test_shortcuts(text: str, expected: tuple) -> None:
    assert query(text) == expected


def test_missing_shortcut_board_is_an_error() -> None:
    result = parse("lastweek", boards={"daily": make_board(name="daily")})
    assert isinstance(result, CommandError) and "no `weekly` board" in result.message


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("weekly daily", "Two boards"),
        ("weekly today yesterday", "Two dates"),
        ("wekly", "I didn't understand `wekly`"),
    ],
)
def test_errors(text: str, message: str) -> None:
    result = parse(text)
    assert isinstance(result, CommandError) and message in result.message
