# T-402 · Command parsing: saved boards, anchors, games, shortcuts

| | |
|---|---|
| **Workstream** | D — Commands & formatting ([plan](../plan/04-commands-formatting.md)) |
| **Depends on** | [T-401](T-401-resolve-anchor.md) |
| **Blocks** | [T-403](T-403-parse-adhoc.md) |
| **Size** | M (1–3 days) |

## Files

- `src/leaderboard/commands.py` (`parse_command`, token index)
- `tests/test_commands.py`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [04-commands-formatting.md](../plan/04-commands-formatting.md) §5.1 (rules 1, 2, 4, 5)

## Scope

- Build the token index from games (id, alias, display name), boards and reserved/anchor words.
- Handle the reserved words, then saved board + anchor + game filter in any order, then the shortcuts (`lastweek` → weekly, `lastmonth` → average, otherwise daily), with `today` as the default anchor.
- An unknown token gives a basic `CommandError` (suggestions come in T-403).

## Acceptance criteria

- [x] The saved-board, anchor, game-filter, shortcut and reserved-word cases in `04-commands-formatting.md` §7.
- [x] `uv run pytest` passes; committed and pushed to `master`
