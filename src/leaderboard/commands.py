"""Parse chat commands (`@leaderboard weekly maptap`) into queries.

Shared by @mentions, the slash command, `leaderboard show` and the scheduler.
See docs/plan/04-commands-formatting.md.
"""

from __future__ import annotations

import difflib
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import TYPE_CHECKING, Literal

from leaderboard.boards.config import POSITIONAL

if TYPE_CHECKING:
    from leaderboard.boards.config import BoardConfig
    from leaderboard.config import GameConfig

ANCHOR_WORDS: frozenset[str] = frozenset({"today", "yesterday", "lastweek", "last_week", "lastmonth", "last_month"})
RESERVED_WORDS: frozenset[str] = frozenset({"help", "games", "boards"})

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class Query:
    board: BoardConfig  # saved or ad hoc
    games: list[str] | None  # None = all applicable
    anchor: date


@dataclass(frozen=True)
class InfoRequest:
    topic: Literal["help", "games", "boards"]


@dataclass(frozen=True)
class CommandError:
    message: str
    suggestions: list[str] = field(default_factory=list)


SHORTCUT_BOARDS = {"lastweek": "weekly", "last_week": "weekly", "lastmonth": "average", "last_month": "average"}
DEFAULT_SHORTCUT = "daily"


def parse_command(
    text: str, *, today: date, games: Mapping[str, GameConfig], boards: Mapping[str, BoardConfig]
) -> Query | InfoRequest | CommandError:
    """Parse the words after `@leaderboard` / `/leaderboard`. Words may come in any order.

    Either a saved board (`weekly maptap lastweek`) or ad-hoc parts (`maptap avg month`,
    `tg median last_n=10`); see docs/plan/04-commands-formatting.md §5.1.
    """
    from leaderboard.boards.registry import AGGREGATORS, WINDOWS  # imported lazily: registries fill at startup

    tokens = text.lower().split()
    if not tokens:
        return InfoRequest("help")
    if tokens[0] in RESERVED_WORDS:
        if len(tokens) > 1:
            return CommandError(f"`{tokens[0]}` doesn't take anything else")
        return InfoRequest(tokens[0])  # type: ignore[arg-type]

    game_tokens = _game_tokens(games)
    value_names = {v for game in games.values() for v in game.value_names()}
    board: BoardConfig | None = None
    anchor: date | None = None
    anchor_token: str | None = None
    selected: list[str] = []
    value: str | None = None
    window: str | None = None
    aggregate: str | None = None
    params: list[tuple[str, str]] = []

    def unknown(token: str) -> CommandError:
        known = [*boards, *game_tokens, *value_names, *AGGREGATORS, *WINDOWS, *ANCHOR_WORDS, *RESERVED_WORDS]
        return CommandError(f"I didn't understand `{token}`", difflib.get_close_matches(token, known, n=3, cutoff=0.6))

    for token in tokens:
        if "=" in token:
            name, _, raw = token.partition("=")
            if not name or not raw:
                return unknown(token)
            params.append((name, raw))
        elif token in RESERVED_WORDS:
            return CommandError(f"`{token}` has to be on its own")
        elif (resolved := resolve_anchor(token, today)) is not None:
            if anchor is not None:
                return CommandError(f"Two dates: `{anchor_token}` and `{token}`; pick one")
            anchor, anchor_token = resolved, token
        elif token in boards:
            if board is not None:
                return CommandError(f"Two boards: `{board.name}` and `{token}`; pick one")
            board = boards[token]
        elif token in game_tokens:
            if game_tokens[token] not in selected:
                selected.append(game_tokens[token])
        elif token in value_names:
            if value is not None and value != token:
                return CommandError(f"Two values: `{value}` and `{token}`; pick one")
            value = token
        elif token in AGGREGATORS:
            if aggregate is not None and aggregate != token:
                return CommandError(f"Two aggregators: `{aggregate}` and `{token}`; pick one")
            aggregate = token
        elif token in WINDOWS:
            if window is not None and window != token:
                return CommandError(f"Two windows: `{window}` and `{token}`; pick one")
            window = token
        else:
            return unknown(token)

    # name=value: `last_n=10` / `top_k_avg=3` name a component (and select it); `k=3` names a
    # parameter of whichever selected ad-hoc component has it.
    component_params: dict[str, dict[str, object]] = {}
    for name, raw in params:
        literal = _literal(raw)
        if name in WINDOWS:
            if window not in (None, name):
                return CommandError(f"Two windows: `{window}` and `{name}`; pick one")
            window = name
            component_params.setdefault(name, {})[POSITIONAL] = literal
        elif name in AGGREGATORS:
            if aggregate not in (None, name):
                return CommandError(f"Two aggregators: `{aggregate}` and `{name}`; pick one")
            aggregate = name
            component_params.setdefault(name, {})[POSITIONAL] = literal
        else:
            owners = [c for c, table in ((window, WINDOWS), (aggregate, AGGREGATORS))
                      if c is not None and table[c].params is not None and name in table[c].params.model_fields]
            if len(owners) != 1:
                return CommandError(f"I don't know which part `{name}=` belongs to" if owners
                                    else f"No selected part takes a `{name}` parameter")
            component_params.setdefault(owners[0], {})[name] = literal  # type: ignore[index]

    adhoc = value is not None or window is not None or aggregate is not None
    if board is not None and adhoc:
        return CommandError("Use either a saved board or ad-hoc parts (value, window, aggregator), not both")

    if adhoc:
        built = _adhoc_board(value or "score", window or "week", aggregate or "best", component_params, selected, games)
        if isinstance(built, CommandError):
            return built
        board = built
    elif board is None:
        shortcut = SHORTCUT_BOARDS.get(anchor_token or "", DEFAULT_SHORTCUT)
        if shortcut not in boards:
            return CommandError(f"There's no `{shortcut}` board in boards.yaml")
        board = boards[shortcut]
    return Query(board, selected or None, anchor or today)


def _adhoc_board(
    value: str, window: str, aggregate: str, params: dict[str, dict[str, object]],
    selected: list[str], games: Mapping[str, GameConfig],
) -> BoardConfig | CommandError:
    from leaderboard.boards.config import BoardConfig, ComponentRef
    from leaderboard.boards.registry import AGGREGATORS, WINDOWS, validate_params

    scope = [games[g] for g in selected] or list(games.values())
    if not any(value in g.value_names() for g in scope):
        where = ", ".join(g.label for g in scope)
        return CommandError(f"`{value}` isn't tracked for {where}")
    try:
        for name, table in ((window, WINDOWS), (aggregate, AGGREGATORS)):
            validate_params(table[name], params.get(name, {}))
    except ValueError as exc:
        return CommandError(str(exc))

    def describe(name: str) -> str:
        shown = [f"{v}" if k == POSITIONAL else f"{k}={v}" for k, v in params.get(name, {}).items()]
        return f"{name} {' '.join(shown)}" if shown else name

    parts = ([", ".join(games[g].label for g in selected)] if selected else []) + \
        ([value] if value != "score" else []) + [describe(aggregate), describe(window)]
    return BoardConfig(
        name="adhoc",
        title=" · ".join(parts),
        value=value,
        window=ComponentRef(name=window, params=params.get(window, {})),
        aggregate=ComponentRef(name=aggregate, params=params.get(aggregate, {})),
    )


def _literal(raw: str) -> object:
    for convert in (int, float):
        try:
            return convert(raw)
        except ValueError:
            pass
    return raw


def _game_tokens(games: Mapping[str, GameConfig]) -> dict[str, str]:
    """Every word that names a game (id, alias, one-word display name) → the game's id."""
    tokens: dict[str, str] = {}
    for game in games.values():
        for token in (game.name, *game.aliases, game.display_name or ""):
            if token:
                tokens[token.lower()] = game.name
    return tokens


def resolve_anchor(token: str, today: date) -> date | None:
    """Resolve an anchor word or `YYYY-MM-DD` to a date; `None` if `token` isn't an anchor.

    Windows end at the anchor, so "last week" is the previous Sunday (the `week` window then
    covers that whole Mon–Sun week) and "last month" is the previous month's last day.
    Accepts both `lastweek` (typed in chat) and `last_week` (boards.yaml schedule anchors).
    """
    match token.lower():
        case "today":
            return today
        case "yesterday":
            return today - timedelta(days=1)
        case "lastweek" | "last_week":
            return today - timedelta(days=today.weekday() + 1)
        case "lastmonth" | "last_month":
            return today.replace(day=1) - timedelta(days=1)
    try:
        return date.fromisoformat(token) if _ISO_DATE.match(token) else None
    except ValueError:
        return None
