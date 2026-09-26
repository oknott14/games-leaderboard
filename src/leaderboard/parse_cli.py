"""`leaderboard parse`: show what the game configs extract from a share text.

    pbpaste | leaderboard parse
    leaderboard parse "TimeGuessr #512 38,532/50,000"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TextIO

from leaderboard.config import GameConfig, load_games
from leaderboard.parser import ParsedResult, load_plugin_parser, parse_message

LABEL_WIDTH = 14


def parse_main(argv: list[str] | None = None, *, stdin: TextIO | None = None, out: TextIO | None = None) -> int:
    stdin = stdin or sys.stdin
    out = out or sys.stdout
    parser = argparse.ArgumentParser(prog="leaderboard parse", description=__doc__.splitlines()[0])
    parser.add_argument("text", nargs="?", help="share text (default: read stdin)")
    parser.add_argument("--games-dir", type=Path, default=Path("games"))
    parser.add_argument("--plugins-dir", type=Path, default=Path("plugins"), help="for games with `parser:`")
    parser.add_argument("--all-games", action="store_true", help="also list games that weren't detected")
    args = parser.parse_args(argv)

    if args.plugins_dir.is_dir() and str(args.plugins_dir) not in sys.path:
        sys.path.insert(0, str(args.plugins_dir))
    try:
        games = load_games(args.games_dir)
        for game in games.values():
            if game.parser is not None:
                load_plugin_parser(game)  # fail fast with a clear message
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    text = _normalize(args.text if args.text is not None else stdin.read())
    results = parse_message(text, games.values())
    by_game = {r.game: r for r in results}

    if not results:
        print("No game detected.", file=out)
    for game in games.values():
        if game.name in by_game:
            print(_describe(game, by_game[game.name]), file=out)
        elif args.all_games:
            print(f"{_label(game)}(not detected)", file=out)
    return 0


def _normalize(text: str) -> str:
    """Apply the Slack adapter's normalisation, so pasted Slack text parses as it would live."""
    from leaderboard.adapters.slack import normalize_text

    try:
        return normalize_text(text)
    except NotImplementedError:
        print("note: Slack text normalisation isn't implemented yet; parsing the text as-is", file=sys.stderr)
        return text


def _describe(game: GameConfig, result: ParsedResult) -> str:
    rounds = f"[{', '.join(_num(r) for r in result.rounds)}]" if result.rounds else "-"
    line = f"{_label(game)}score={_num(result.score)}  rounds={rounds}  puzzle={result.puzzle or '-'}"
    extra = [n for n in game.value_names() if n != "score"]
    if extra:
        values = "  ".join(f"{n}={_num(game.value(n, result.score, result.rounds))}" for n in extra)
        line += "\n" + " " * LABEL_WIDTH + values
    return line


def _label(game: GameConfig) -> str:
    """The game's label padded to the column, always followed by at least two spaces."""
    return f"{game.label:<{LABEL_WIDTH - 2}}  "


def _num(value: float | None) -> str:
    if value is None:
        return "-"
    return str(int(value)) if float(value).is_integer() else f"{value:.1f}"
