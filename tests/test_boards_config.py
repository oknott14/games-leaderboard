from __future__ import annotations

import logging
from pathlib import Path

import pytest
from conftest import sample_games

from leaderboard.boards.config import check_token_collisions, load_boards
from leaderboard.boards.registry import load_builtins

load_builtins()
GAMES = sample_games()


def load(tmp_path: Path, body: str):  # noqa: ANN201
    path = tmp_path / "boards.yaml"
    path.write_text(body)
    return load_boards(path, GAMES)


def rejects(tmp_path: Path, body: str, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        load(tmp_path, body)


def test_valid_file_with_defaults_merged(tmp_path: Path) -> None:
    parsed = load(tmp_path, """
defaults: { min_entries: 2, limit: 5 }
boards:
  weekly:  { window: week, aggregate: sum }
  strict:  { window: month, aggregate: avg, min_entries: 5 }
  recent:  { window: { last_n: 3 }, aggregate: avg }
  top3:    { aggregate: { top_k_avg: { k: 3 } } }
schedule:
  - { cron: "0 9 * * MON", boards: [weekly], anchor: last_week }
""")
    assert (parsed.boards["weekly"].min_entries, parsed.boards["weekly"].limit) == (2, 5)
    assert parsed.boards["strict"].min_entries == 5  # the board overrides the default
    assert parsed.boards["recent"].window.name == "last_n"
    assert parsed.schedule[0].anchor == "last_week"


def test_board_with_no_body_gets_defaults(tmp_path: Path) -> None:
    parsed = load(tmp_path, "defaults: { window: month }\nboards:\n  plain:\n")
    assert parsed.boards["plain"].window.name == "month"


def test_missing_file_is_empty_with_warning(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        parsed = load_boards(tmp_path / "nope.yaml", GAMES)
    assert parsed.boards == {} and parsed.schedule == []
    assert "not found" in caplog.text


def test_empty_file(tmp_path: Path) -> None:
    assert load(tmp_path, "").boards == {}


@pytest.mark.parametrize(
    ("body", "match"),
    [
        ("boards: { b: { window: fortnight } }", r"boards.yaml: board 'b': unknown window 'fortnight' \(available: all, day"),
        ("boards: { b: { aggregate: mode } }", "board 'b': unknown aggregate 'mode'"),
        ("boards: { b: { type: podium } }", "board 'b': unknown type 'podium'"),
        ("boards: { b: { window: { last_n: 0 } } }", "board 'b': last_n: invalid parameters"),
        ("boards: { b: { window: { week: 3 } } }", r"board 'b': week takes no parameters"),
        ("boards: { b: { value: fastest } }", "board 'b': no game defines the value 'fastest'"),
        ("boards: { b: { games: [wordle] } }", r"board 'b': unknown game\(s\) \['wordle'\]"),
        ("boards: { b: { value: best_round, games: [timeguessr] } }", "isn't defined by \\['timeguessr'\\]"),
        ("boards: { b: {} }\nschedule: [ { cron: '0 9 * * *', boards: [nope] } ]", r"schedule\[0\]: unknown board"),
        ("boards: { b: {} }\nschedule: [ { cron: 'every day', boards: [b] } ]", r"schedule\[0\]: invalid cron"),
        ("boards: { b: { windw: week } }", "(?s)boards.yaml: .*Extra inputs"),
        ("- just\n- a list\n", "expected a mapping"),
        ("boards: [a, b]", "must be mappings"),
        ("boards: { b: [unclosed", "boards.yaml: "),
    ],
)
def test_rejections(tmp_path: Path, body: str, match: str) -> None:
    rejects(tmp_path, body, match)


def test_value_available_in_some_games_is_fine(tmp_path: Path) -> None:
    assert load(tmp_path, "boards: { r: { value: best_round } }").boards["r"].value == "best_round"


# ── token collisions (T-323) ──


@pytest.mark.parametrize(
    ("body", "match"),
    [
        ("boards: { help: {} }", "'help' is both a reserved command word and board 'help'"),
        ("boards: { yesterday: {} }", "'yesterday' is both an anchor word and board 'yesterday'"),
        ("boards: { week: {} }", "'week' is both window 'week' and board 'week'"),
        ("boards: { avg: {} }", "'avg' is both aggregator 'avg' and board 'avg'"),
        ("boards: { maptap: {} }", "'maptap' is both game 'maptap' and board 'maptap'"),
        ("boards: { tg: {} }", "'tg' is both game 'timeguessr' and board 'tg'"),
        ("boards: { best_round: {} }", "'best_round' is both value 'best_round' and board 'best_round'"),
    ],
)
def test_board_name_collisions(tmp_path: Path, body: str, match: str) -> None:
    rejects(tmp_path, body, "boards.yaml: name collision: " + match)


def test_game_alias_colliding_with_an_aggregator() -> None:
    games = sample_games()
    games["maptap"] = games["maptap"].model_copy(update={"aliases": ["best"]})
    with pytest.raises(ValueError, match="'best' is both aggregator 'best' and game 'maptap'"):
        check_token_collisions({}, games)


def test_value_named_like_a_window() -> None:
    games = sample_games()
    krillion = games["krillion"]
    games["krillion"] = krillion.model_copy(update={"values": krillion.values | {"day": krillion.values["best_round"]}})
    with pytest.raises(ValueError, match="'day' is both window 'day' and value 'day'"):
        check_token_collisions({}, games)


def test_collisions_are_case_insensitive() -> None:
    games = sample_games()
    games["maptap"] = games["maptap"].model_copy(update={"aliases": ["HELP"]})
    with pytest.raises(ValueError, match="'HELP' is both a reserved command word and game 'maptap'"):
        check_token_collisions({}, games)


def test_repeated_value_names_across_games_are_fine() -> None:
    check_token_collisions({}, sample_games())  # maptap and krillion both define best_round
