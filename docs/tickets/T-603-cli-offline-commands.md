# T-603 · CLI: reparse, show, parse

| | |
|---|---|
| **Workstream** | F — Runtime: settings, CLI & scheduler ([plan](../plan/06-runtime.md)) |
| **Depends on** | [T-602](T-602-cli-skeleton-check.md), [T-203](T-203-reparse.md), [T-206](T-206-on-command.md), [T-108](T-108-parse-cli.md) |
| **Blocks** | [T-704](T-704-user-readme.md) |
| **Size** | S (≤ 1 day) |

## Files

- `src/leaderboard/cli.py`
- `tests/test_cli.py`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [06-runtime.md](../plan/06-runtime.md) §5.3

## Scope

- `reparse` prints the count. `show <words…>` prints `service.on_command(...)`, using Slack names when a token is set and user ids otherwise. `parse` delegates to `parse_main`.

## Acceptance criteria

- [ ] `show weekly` against a temporary DB prints a board.
- [ ] `parse` delegates correctly.
- [ ] `reparse` prints the count.
- [ ] `uv run pytest` passes; PR reviewed and merged
