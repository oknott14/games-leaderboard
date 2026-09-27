"""Command-line entry point (`leaderboard`).

    leaderboard check            validate games/, boards.yaml and plugins/
    leaderboard parse [TEXT]     show what the game configs extract from a share text
    leaderboard show WORDS…      print a board, exactly as the bot would reply
    leaderboard reparse          rebuild results from stored messages
    leaderboard backfill         pull channel history from Slack
    leaderboard run              run the bot

Settings come from environment variables (see .env.example); natively, use
`uv run --env-file .env leaderboard …`.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Callable, Mapping

from leaderboard.boards.config import BoardsFile, load_boards
from leaderboard.boards.registry import AGGREGATORS, BOARD_TYPES, WINDOWS, load_builtins, load_plugins
from leaderboard.config import GameConfig, load_games
from leaderboard.formatting import composition
from leaderboard.parser import load_plugin_parser
from leaderboard.settings import Settings

log = logging.getLogger(__name__)

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    settings = Settings.from_env()
    logging.basicConfig(level=args.log_level or settings.log_level, format=LOG_FORMAT)
    return COMMANDS[args.command](args, settings)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="leaderboard", description="Games leaderboard bot",
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--log-level", help="override LOG_LEVEL (DEBUG, INFO, WARNING, …)")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.add_parser("check", help="validate games, boards.yaml and plugins, and list what's registered")
    return parser


def load_all(settings: Settings) -> tuple[dict[str, GameConfig], BoardsFile, list[str]]:
    """Load built-ins, plugins, games and boards.yaml, in that order. Any config error prints
    the message (which names the file) and exits with code 2, so the bot never starts
    half-configured. Returns the games, the boards file and the plugin-registered names."""
    try:
        load_builtins()
        plugin_names = load_plugins(settings.plugins_dir)
        games = load_games(settings.games_dir)
        for game in games.values():
            if game.parser is not None:
                load_plugin_parser(game)
        boards = load_boards(settings.boards_file, games)
    except (ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from None
    return games, boards, plugin_names


def cmd_check(args: argparse.Namespace, settings: Settings) -> int:
    games, boards, plugins = load_all(settings)

    def names(table: Mapping[str, object]) -> str:
        return ", ".join(f"{n}*" if n in plugins else n for n in table)

    print(f"Games ({len(games)}):")
    for game in games.values():
        source = f"parser {game.parser}" if game.parser else "regex"
        print(f"  {game.name:<14}{game.label} [{', '.join(game.aliases) or '-'}] ({source}) "
              f"values: {', '.join(game.value_names())}")
    print(f"Boards ({len(boards.boards)}):")
    for name, board in boards.boards.items():
        print(f"  {name:<14}{board.title or name} ({composition(board)})")
    print(f"Windows: {names(WINDOWS)}")
    print(f"Aggregators: {names(AGGREGATORS)}")
    print(f"Board types: {names(BOARD_TYPES)}")
    if plugins:
        print("  (* = from plugins)")
    print(f"Schedule ({len(boards.schedule)}):")
    for entry in boards.schedule:
        print(f"  {entry.cron:<14}{', '.join(entry.boards)} (anchor: {entry.anchor})")
    print("OK")
    return 0


COMMANDS: dict[str, Callable[[argparse.Namespace, Settings], int]] = {
    "check": cmd_check,
}
