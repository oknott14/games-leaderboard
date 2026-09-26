from __future__ import annotations

import logging

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
