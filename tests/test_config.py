from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from leaderboard.config import GameConfig, NumberSpec, load_games, parse_number

BASE: dict[str, Any] = {"name": "g", "detect": "G #\\d+", "score": {"pattern": "(?P<value>\\d+)"}}
ROUNDS = {"block": "(?P<block>.+)", "item": "\\d+"}


def game(**overrides: Any) -> GameConfig:
    return GameConfig.model_validate(BASE | overrides)


def rejects(match: str, **overrides: Any) -> None:
    with pytest.raises(ValidationError, match=re.escape(match)):
        game(**overrides)


# ── parse_number ──


@pytest.mark.parametrize(
    ("raw", "spec", "expected"),
    [
        ("38,532", NumberSpec(), 38532.0),
        (" 7 ", NumberSpec(), 7.0),
        ("1_000", NumberSpec(), 1000.0),
        ("1 000", NumberSpec(), 1000.0),
        ("X", NumberSpec(map={"X": 7}), 7.0),
        (" X ", NumberSpec(map={"X": 7}), 7.0),
        ("🌟", NumberSpec(map={"🌟": 100}), 100.0),
        ("4.25", NumberSpec(type="float"), 4.25),
        ("4.25", NumberSpec(), None),  # int spec rejects decimals
        ("abc", NumberSpec(), None),
        ("", NumberSpec(), None),
        ("12abc", NumberSpec(type="float"), None),
    ],
)
def test_parse_number(raw: str, spec: NumberSpec, expected: float | None) -> None:
    result = parse_number(raw, spec)
    assert result == expected
    assert result is None or isinstance(result, float)


# ── valid configs ──


def test_minimal_game_is_valid() -> None:
    assert game().name == "g"


def test_from_rounds_score_with_rounds_is_valid() -> None:
    assert game(score={"from_rounds": "sum"}, rounds=ROUNDS).score.from_rounds == "sum"  # type: ignore[union-attr]


def test_plugin_parser_game_is_valid() -> None:
    g = GameConfig.model_validate({"name": "g", "parser": "my_plugins.krillion:parse",
                                   "values": {"best_round": {"from_rounds": "max"}}})
    assert g.parser == "my_plugins.krillion:parse"


def test_flags_apply_to_validation() -> None:
    assert game(flags=["IGNORECASE", "MULTILINE"]).re_flags == re.IGNORECASE | re.MULTILINE


def test_compiled_patterns_are_cached_and_flagged() -> None:
    g = game(flags=["IGNORECASE"], rounds=ROUNDS, puzzle={"pattern": "#(?P<value>\\d+)"})
    assert g.detect_re is g.detect_re
    assert g.detect_re is not None and g.detect_re.flags & re.IGNORECASE
    assert all(p is not None for p in (g.score_re, g.puzzle_re, g.block_re, g.item_re))
    assert game().block_re is None and game().puzzle_re is None


# ── invalid configs (01-parsing.md §7, except the cross-file cases) ──


def test_bad_regex_names_the_field() -> None:
    rejects("detect: invalid regex", detect="G (")
    rejects("score.pattern: invalid regex", score={"pattern": "(?P<value>\\d+"})
    rejects("rounds.item: invalid regex", rounds=ROUNDS | {"item": "["})


def test_missing_named_groups() -> None:
    rejects("score.pattern: must contain a named group (?P<value>", score={"pattern": "(\\d+)"})
    rejects("puzzle.pattern: must contain a named group (?P<value>", puzzle={"pattern": "#\\d+"})
    rejects("rounds.block: must contain a named group (?P<block>", rounds=ROUNDS | {"block": "(.+)"})


def test_score_needs_exactly_one_source() -> None:
    rejects("score: set exactly one of", score={})
    rejects("score: set exactly one of", score={"pattern": "(?P<value>\\d+)", "from_rounds": "sum"}, rounds=ROUNDS)


def test_from_rounds_requires_rounds() -> None:
    rejects("score.from_rounds: requires a `rounds` section", score={"from_rounds": "sum"})
    rejects("values.best.from_rounds: requires a `rounds` section", values={"best": {"from_rounds": "max"}})


def test_needs_parser_or_detect_and_score() -> None:
    with pytest.raises(ValidationError, match="either `parser`, or both `detect` and `score`"):
        GameConfig.model_validate({"name": "g", "detect": "x"})
    with pytest.raises(ValidationError, match="parser: can't be combined with detect"):
        GameConfig.model_validate(BASE | {"parser": "m:f"})
    with pytest.raises(ValidationError, match="parser: expected 'module:function'"):
        GameConfig.model_validate({"name": "g", "parser": "not a ref"})


def test_value_names() -> None:
    rejects("values: 'score' is reserved", rounds=ROUNDS, values={"score": {"from_rounds": "sum"}})
    rejects("values: name 'Best-Round' must match", rounds=ROUNDS, values={"Best-Round": {"from_rounds": "max"}})


def test_item_allows_at_most_one_group() -> None:
    rejects("rounds.item: use at most one capturing group", rounds=ROUNDS | {"item": "(\\d)(\\d)"})
    assert game(rounds=ROUNDS | {"item": "(?:ab)(\\d)"}).rounds is not None  # non-capturing is fine


def test_check_sum_needs_a_score_pattern() -> None:
    rejects("rounds.check_sum: needs `score.pattern`",
            score={"from_rounds": "sum"}, rounds=ROUNDS | {"check_sum": True})


def test_unknown_key_rejected() -> None:
    rejects("Extra inputs are not permitted", detcet="typo")


# ── load_games ──

MAPTAP_YAML = """
display_name: MapTap
aliases: [map]
detect: 'maptap\\.gg'
score: { pattern: 'final score:?\\s*(?P<value>[\\d,]+)' }
"""


def write(directory: Path, name: str, body: str) -> Path:
    path = directory / name
    path.write_text(body)
    return path


def test_load_games_reads_yaml_and_yml_in_sorted_order(tmp_path: Path) -> None:
    write(tmp_path, "zeta.yml", "detect: z\nscore: { pattern: '(?P<value>\\d+)' }\n")
    write(tmp_path, "maptap.yaml", MAPTAP_YAML)
    write(tmp_path, "notes.txt", "ignored")
    games = load_games(tmp_path)
    assert list(games) == ["maptap", "zeta"]
    assert games["zeta"].name == "zeta"  # defaults to the file stem


def test_load_games_explicit_name_wins(tmp_path: Path) -> None:
    write(tmp_path, "map.yaml", "name: maptap\n" + MAPTAP_YAML)
    assert list(load_games(tmp_path)) == ["maptap"]


def test_load_games_skips_disabled(tmp_path: Path) -> None:
    write(tmp_path, "maptap.yaml", MAPTAP_YAML)
    write(tmp_path, "krillion.yaml", "enabled: false\ndetect: k\nscore: { pattern: '(?P<value>\\d+)' }\n")
    assert list(load_games(tmp_path)) == ["maptap"]


def test_disabled_games_dont_reserve_tokens(tmp_path: Path) -> None:
    write(tmp_path, "a.yaml", "enabled: false\naliases: [map]\ndetect: a\nscore: { pattern: '(?P<value>\\d+)' }\n")
    write(tmp_path, "maptap.yaml", MAPTAP_YAML)
    assert list(load_games(tmp_path)) == ["maptap"]


def test_duplicate_alias_across_files_names_the_second_file(tmp_path: Path) -> None:
    write(tmp_path, "maptap.yaml", MAPTAP_YAML)
    second = write(tmp_path, "other.yaml", "aliases: [MAP]\ndetect: o\nscore: { pattern: '(?P<value>\\d+)' }\n")
    with pytest.raises(ValueError, match=rf"^{re.escape(str(second))}: 'MAP' is already used by game 'maptap'"):
        load_games(tmp_path)


def test_alias_colliding_with_another_games_name(tmp_path: Path) -> None:
    write(tmp_path, "maptap.yaml", MAPTAP_YAML)
    write(tmp_path, "other.yaml", "aliases: [maptap]\ndetect: o\nscore: { pattern: '(?P<value>\\d+)' }\n")
    with pytest.raises(ValueError, match="'maptap' is already used by game 'maptap'"):
        load_games(tmp_path)


def test_game_may_repeat_its_own_name_as_display_name(tmp_path: Path) -> None:
    write(tmp_path, "maptap.yaml", MAPTAP_YAML + "\n")  # display "MapTap" == name "maptap" ignoring case
    assert "maptap" in load_games(tmp_path)


def test_malformed_yaml_names_the_file(tmp_path: Path) -> None:
    bad = write(tmp_path, "broken.yaml", "detect: [unclosed\n")
    with pytest.raises(ValueError, match=rf"^{re.escape(str(bad))}: "):
        load_games(tmp_path)


def test_invalid_game_names_the_file(tmp_path: Path) -> None:
    bad = write(tmp_path, "bad.yaml", "detect: '('\nscore: { pattern: '(?P<value>\\d+)' }\n")
    with pytest.raises(ValueError, match=rf"(?s)^{re.escape(str(bad))}: .*detect: invalid regex"):
        load_games(tmp_path)


def test_non_mapping_yaml_rejected(tmp_path: Path) -> None:
    bad = write(tmp_path, "list.yaml", "- a\n- b\n")
    with pytest.raises(ValueError, match="expected a mapping"):
        load_games(tmp_path)


def test_missing_directory(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="games directory not found"):
        load_games(tmp_path / "nope")


def test_empty_file_uses_stem_but_is_invalid(tmp_path: Path) -> None:
    write(tmp_path, "empty.yaml", "")
    with pytest.raises(ValueError, match="either `parser`"):
        load_games(tmp_path)
