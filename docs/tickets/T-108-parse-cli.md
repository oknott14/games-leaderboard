# T-108 · `leaderboard parse` debugging tool

| | |
|---|---|
| **Workstream** | A — Parsing & game configs ([plan](../plan/01-parsing.md)) |
| **Depends on** | [T-102](T-102-load-games.md), [T-103](T-103-parse-message.md) |
| **Blocks** | [T-603](T-603-cli-offline-commands.md) |
| **Size** | S (≤ 1 day) |

## Files

- `src/leaderboard/parse_cli.py`
- `tests/test_parse_cli.py`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [01-parsing.md](../plan/01-parsing.md) §5.7

## Scope

- `parse_main(argv) -> int`: takes the text from the argument or stdin, and `--games-dir` (default `games`).
- If available, run `adapters.slack.normalize_text` (a lazy import; skip it with a note if it isn't implemented yet).
- Print each result (score, rounds, puzzle, all derived values), or `No game detected.`. `--all-games` also lists the non-matching games.
- Exit 0. Invalid configs exit 2 with the error message.

## Acceptance criteria

- [ ] Output matches the format in `01-parsing.md` §5.7 for the MapTap sample.
- [ ] Stdin input works (`capsys` / monkeypatched stdin).
- [ ] `uv run pytest` passes; PR reviewed and merged

## Notes

- T-603 hooks this up as the `leaderboard parse` subcommand.
