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
import ssl
import sys
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING

from leaderboard.boards.config import BoardsFile, load_boards
from leaderboard.boards.registry import AGGREGATORS, BOARD_TYPES, WINDOWS, load_builtins, load_plugins
from leaderboard.config import GameConfig, load_games
from leaderboard.db import make_session_factory
from leaderboard.formatting import NameFor, composition
from leaderboard.parse_cli import parse_main
from leaderboard.parser import load_plugin_parser
from leaderboard.service import LeaderboardService
from leaderboard.settings import Settings

if TYPE_CHECKING:
    from leaderboard.adapters.slack import SlackPort
    from leaderboard.ports import ChatPort

log = logging.getLogger(__name__)

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args, extra = parser.parse_known_args(argv)
    if args.command == "parse":
        args.rest = [*extra, *args.rest]  # `parse` passes its own flags (e.g. --all-games) through
    elif extra:
        parser.error(f"unrecognized arguments: {' '.join(extra)}")
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
    parse = sub.add_parser("parse", help="show what the game configs extract from a share text", add_help=False)
    parse.add_argument("rest", nargs=argparse.REMAINDER)
    show = sub.add_parser("show", help="print a board as the bot would reply, e.g. `show weekly maptap`")
    show.add_argument("words", nargs="*")
    sub.add_parser("reparse", help="rebuild all results from stored messages (after editing games/)")
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


def cmd_parse(args: argparse.Namespace, settings: Settings) -> int:
    defaults = ["--games-dir", str(settings.games_dir), "--plugins-dir", str(settings.plugins_dir)]
    return parse_main([*defaults, *args.rest])  # flags given explicitly come later and win


def cmd_show(args: argparse.Namespace, settings: Settings) -> int:
    games, boards, _ = load_all(settings)
    name_for: NameFor = lambda platform, user_id: user_id  # noqa: E731
    if settings.slack_bot_token:
        name_for = names_from(_slack_port(settings))
    print(make_service(settings, games, boards, name_for).on_command(" ".join(args.words)))
    return 0


def cmd_reparse(args: argparse.Namespace, settings: Settings) -> int:
    games, boards, _ = load_all(settings)
    count = make_service(settings, games, boards, lambda platform, user_id: user_id).reparse()
    print(f"Reparsed stored messages: {count} results")
    return 0


def names_from(port: ChatPort) -> NameFor:
    """Adapt a port's `display_name(user_id)` to the service's `name_for(platform, user_id)`."""
    return lambda platform, user_id: port.display_name(user_id)


def make_service(settings: Settings, games: Mapping[str, GameConfig], boards: BoardsFile,
                 name_for: NameFor) -> LeaderboardService:
    return LeaderboardService(
        make_session_factory(settings.database_url), games, boards, settings.timezone, settings.channel_ids,
        name_for, store_non_game=settings.store_non_game_messages,
    )


def _slack_port(settings: Settings) -> SlackPort:
    from leaderboard.adapters.slack import SlackPort  # only commands that talk to Slack import it

    try:
        return SlackPort(settings.slack_bot_token, settings.slack_app_token, proxy=settings.https_proxy,
                         ssl_context=_ssl_context(settings))
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from None


def _ssl_context(settings: Settings) -> ssl.SSLContext | None:
    """Trust the corporate root CA in SSL_CERT_FILE (for TLS-inspecting proxies)."""
    if settings.ssl_cert_file is None:
        return None
    if not settings.ssl_cert_file.is_file():
        print(f"error: SSL_CERT_FILE {settings.ssl_cert_file} not found", file=sys.stderr)
        raise SystemExit(2)
    return ssl.create_default_context(cafile=str(settings.ssl_cert_file))


COMMANDS: dict[str, Callable[[argparse.Namespace, Settings], int]] = {
    "check": cmd_check,
    "parse": cmd_parse,
    "show": cmd_show,
    "reparse": cmd_reparse,
}
