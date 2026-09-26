from __future__ import annotations

import importlib
import logging
import re

import pytest
from conftest import SAMPLES, sample_games

from leaderboard.config import GameConfig
from leaderboard.parser import ParsedResult, parse_message

GAMES = sample_games()


def parse(text: str, *names: str) -> list[ParsedResult]:
    return parse_message(text, [GAMES[n] for n in names] if names else GAMES.values())


def only(text: str) -> ParsedResult:
    (result,) = parse(text)
    return result


def test_timeguessr_score_and_puzzle() -> None:
    result = only(SAMPLES["timeguessr_basic"])
    assert (result.game, result.score, result.puzzle) == ("timeguessr", 38532.0, "512")


def test_maptap_score() -> None:
    result = only(SAMPLES["maptap_basic"])
    assert (result.game, result.score, result.puzzle) == ("maptap", 862.0, None)


@pytest.mark.parametrize("sample", ["krillion_basic", "krillion_slack"])
def test_krillion_score_and_puzzle(sample: str) -> None:
    result = only(SAMPLES[sample])
    assert (result.game, result.score, result.puzzle) == ("krillion", 505.0, "72")


def test_krillion_puzzle_number_never_read_as_score() -> None:
    assert only("Krillion #72 🦐\n505\n\n🏮").score == 505.0
    assert parse("Krillion #72 🦐\n\n🏮🌟") == []  # no score line: not 72


def test_two_games_in_one_message_in_games_order() -> None:
    results = parse(SAMPLES["two_games_one_message"])
    assert [(r.game, r.score) for r in results] == [("timeguessr", 38532.0), ("krillion", 505.0)]


def test_only_listed_games_are_considered() -> None:
    assert [r.game for r in parse(SAMPLES["two_games_one_message"], "krillion")] == ["krillion"]


def test_non_game_message() -> None:
    assert parse(SAMPLES["not_a_game"]) == []
    assert parse("") == []


def test_detected_without_score_warns_and_skips(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="leaderboard.parser"):
        assert parse("TimeGuessr #512 (forgot to paste the score)") == []
    (record,) = caplog.records
    assert "timeguessr: detected, but no score" in record.getMessage()
    assert "TimeGuessr #512" in record.getMessage()


def test_warning_truncates_long_text(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="leaderboard.parser"):
        parse("TimeGuessr #1 " + "x" * 500)
    assert len(caplog.records[0].getMessage()) < 200


def test_unparseable_score_warns(caplog: pytest.LogCaptureFixture) -> None:
    game = GameConfig(name="g", detect="G!", score={"pattern": r"score (?P<value>\S+)"})
    with caplog.at_level(logging.WARNING):
        assert parse_message("G! score lots", [game]) == []
    assert "g: detected, but no score" in caplog.text


def test_no_warning_for_undetected_games(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        parse(SAMPLES["krillion_basic"])
    assert caplog.records == []


# ── rounds (T-104) ──

KRILLION_ROUNDS = (85.0, 100.0, 30.0, 85.0, 85.0, 60.0, 60.0)


def test_maptap_horizontal_rounds_exclude_date_and_total() -> None:
    assert only(SAMPLES["maptap_basic"]).rounds == (93.0, 88.0, 71.0, 97.0, 85.0)


def test_maptap_rounds_after_slack_link_normalisation_shape() -> None:
    # the adapter turns <url|label> into the label; the raw form still detects and scores
    result = only(SAMPLES["maptap_slack_raw"])
    assert result.score == 862.0


@pytest.mark.parametrize("sample", ["krillion_basic", "krillion_slack"])
def test_krillion_tiles_map_to_round_values(sample: str) -> None:
    result = only(SAMPLES[sample])
    assert result.rounds == KRILLION_ROUNDS and sum(result.rounds) == result.score


@pytest.mark.parametrize(
    "text",
    [
        "Krillion #72 :shrimp:\n505\n:izakaya_lantern::star2::fish::izakaya_lantern::izakaya_lantern::squid::squid:",
        "Krillion #72 🦐\n505\n\n🏮🌟🐟🏮🏮🦑🦑\nugh, the squids 🦑",  # chatter after the tiles
        "lol rough one\nKrillion #72 🦐\n505\n\n🏮🌟🐟🏮🏮🦑🦑",  # chatter before
    ],
)
def test_krillion_layout_variants(text: str) -> None:
    result = only(text)
    assert (result.score, result.rounds) == (505.0, KRILLION_ROUNDS)


def test_krillion_bubbles_and_lantern_alias() -> None:
    result = only("Krillion #73 :shrimp:\n225\n\n:bubbles::lantern::fish::bubbles::fish::fish::bubbles:")
    assert result.rounds == (10.0, 85.0, 30.0, 10.0, 30.0, 30.0, 10.0)


VERTICAL = GameConfig.model_validate({
    "name": "vert",
    "flags": ["MULTILINE"],
    "detect": r"^Vert #\d+",
    "score": {"pattern": r"^Total: (?P<value>[\d,]+)"},
    "rounds": {"block": r"^Vert #\d+\n(?P<block>(?:[^\n]*\n)*?)Total", "item": r"^\s*(\d[\d,]*)"},
})


def test_vertical_rounds_one_per_line() -> None:
    (result,) = parse_message("Vert #9\n 1,200\n  900\n 3\nTotal: 2,103", [VERTICAL])
    assert (result.score, result.rounds) == (2103.0, (1200.0, 900.0, 3.0))


def test_score_from_rounds() -> None:
    game = GameConfig.model_validate({
        "name": "summed", "detect": "Summed", "score": {"from_rounds": "sum"},
        "rounds": {"block": r"Summed: (?P<block>.*)", "item": r"\d+"},
    })
    (result,) = parse_message("Summed: 10 20 30", [game])
    assert (result.score, result.rounds) == (60.0, (10.0, 20.0, 30.0))


def test_score_from_rounds_without_rounds_warns(caplog: pytest.LogCaptureFixture) -> None:
    game = GameConfig.model_validate({
        "name": "summed", "detect": "Summed", "score": {"from_rounds": "sum"},
        "rounds": {"block": r"Summed: (?P<block>.*)", "item": r"\d+"},
    })
    with caplog.at_level(logging.WARNING):
        assert parse_message("Summed (no rounds today)", [game]) == []
    assert "no score" in caplog.text


def test_item_map_converts_emoji() -> None:
    game = GameConfig.model_validate({
        "name": "squares", "detect": "Squares", "score": {"from_rounds": "sum"},
        "rounds": {"block": r"Squares\n(?P<block>.+)", "item": r":\w+:",
                   "map": {":large_green_square:": 2, ":large_yellow_square:": 1, ":black_large_square:": 0}},
    })
    (result,) = parse_message("Squares\n:large_green_square::black_large_square::large_yellow_square:", [game])
    assert (result.rounds, result.score) == ((2.0, 0.0, 1.0), 3.0)


def test_unmappable_item_is_skipped_with_warning(caplog: pytest.LogCaptureFixture) -> None:
    game = GameConfig.model_validate({
        "name": "squares", "detect": "Squares", "score": {"pattern": r"= (?P<value>\d+)"},
        "rounds": {"block": r"Squares\n(?P<block>.+)", "item": r":\w+:", "map": {":a:": 1}},
    })
    with caplog.at_level(logging.WARNING):
        (result,) = parse_message("Squares\n:a::mystery::a:\n= 2", [game])
    assert result.rounds == (1.0, 1.0)
    assert "skipping round ':mystery:'" in caplog.text


def test_check_sum_mismatch_warns_and_keeps_posted_score(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        result = only("Krillion #72 🦐\n999\n\n🏮🌟🐟🏮🏮🦑🦑")
    assert result.score == 999.0 and result.rounds == KRILLION_ROUNDS
    assert "add up to 505.0, not the posted score 999.0" in caplog.text


def test_check_sum_match_is_silent(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        only(SAMPLES["krillion_basic"])
    assert caplog.records == []


def test_no_rounds_block_gives_empty_rounds() -> None:
    assert only(SAMPLES["timeguessr_basic"]).rounds == ()
    assert only("Krillion #72 🦐\n505").rounds == ()


# ── code review regressions ──


def test_optional_value_group_that_didnt_match_skips_game(caplog: pytest.LogCaptureFixture) -> None:
    game = GameConfig(name="h", detect="H", score={"pattern": r"H (?P<value>\d+)?"},
                      puzzle={"pattern": r"#(?P<value>\d+)?"})
    with caplog.at_level(logging.WARNING):
        results = parse_message("H nothing #", [game, GAMES["krillion"]])
    assert results == []  # no crash; other games still parsed (none match here)
    assert "h: detected, but no score" in caplog.text


def test_optional_puzzle_group_that_didnt_match_gives_no_puzzle() -> None:
    game = GameConfig(name="h", detect="H", score={"pattern": r"H (?P<value>\d+)"},
                      puzzle={"pattern": r"#(?P<value>\d+)?"})
    (result,) = parse_message("H 5 #", [game])
    assert (result.score, result.puzzle) == (5.0, None)


def test_check_sum_tolerates_float_rounding(caplog: pytest.LogCaptureFixture) -> None:
    game = GameConfig.model_validate({
        "name": "f", "detect": "F", "score": {"pattern": r"= (?P<value>[\d.]+)", "type": "float"},
        "rounds": {"block": r"F (?P<block>[^=]+)", "item": r"[\d.]+", "type": "float", "check_sum": True},
    })
    with caplog.at_level(logging.WARNING):
        (result,) = parse_message("F 0.1 0.2 = 0.3", [game])
    assert result.score == 0.3 and caplog.records == []


def test_check_sum_warns_when_no_rounds_found(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        result = only("Krillion #72 :shrimp:\n505\n\n:new_tile::other_tile:")
    assert (result.score, result.rounds) == (505.0, ())
    assert "check_sum: no rounds found" in caplog.text


# ── plugin parsers (T-106) ──

PLUGIN_SOURCE = '''
from leaderboard.parser import ParsedResult

calls = []

def parse(text):
    calls.append(text)
    if "Weird" not in text:
        return None
    return ParsedResult(game="placeholder", score=42, rounds=(40, 2), puzzle="7")

def broken(text):
    return {"score": 1}

not_a_function = 5
'''


@pytest.fixture
def plugin_module(tmp_path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> str:
    name = "weird_plugin_" + re.sub(r"\W", "_", request.node.name)  # unique per test
    (tmp_path / f"{name}.py").write_text(PLUGIN_SOURCE)
    monkeypatch.syspath_prepend(str(tmp_path))
    return name


def plugin_game(ref: str) -> GameConfig:
    return GameConfig.model_validate({"name": "weird", "parser": ref})


def test_plugin_parser_result_gets_the_game_name(plugin_module: str) -> None:
    (result,) = parse_message("Weird game 42", [plugin_game(f"{plugin_module}:parse")])
    assert result == ParsedResult(game="weird", score=42, rounds=(40, 2), puzzle="7")


def test_plugin_returning_none_gives_no_result(plugin_module: str) -> None:
    assert parse_message("nothing here", [plugin_game(f"{plugin_module}:parse")]) == []


def test_plugin_is_resolved_once(plugin_module: str) -> None:
    game = plugin_game(f"{plugin_module}:parse")
    parse_message("a", [game])
    parse_message("b", [game])
    assert importlib.import_module(plugin_module).calls == ["a", "b"]


def test_plugin_and_regex_games_mix(plugin_module: str) -> None:
    games = [GAMES["krillion"], plugin_game(f"{plugin_module}:parse")]
    results = parse_message(SAMPLES["krillion_basic"] + "\nWeird 42", games)
    assert [r.game for r in results] == ["krillion", "weird"]


@pytest.mark.parametrize(
    ("func", "match"),
    [("missing", "can't load parser"), ("not_a_function", "is not callable")],
)
def test_bad_plugin_reference_is_a_clear_error(plugin_module: str, func: str, match: str) -> None:
    with pytest.raises(ValueError, match=rf"game 'weird': .*{match}"):
        parse_message("x", [plugin_game(f"{plugin_module}:{func}")])


def test_missing_plugin_module_is_a_clear_error() -> None:
    with pytest.raises(ValueError, match="game 'weird': can't load parser 'no_such_module_xyz:parse'"):
        parse_message("x", [plugin_game("no_such_module_xyz:parse")])


def test_plugin_returning_wrong_type_is_ignored(plugin_module: str, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        assert parse_message("x", [plugin_game(f"{plugin_module}:broken")]) == []
    assert "not a ParsedResult" in caplog.text
