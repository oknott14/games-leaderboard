# T-601 · Settings from environment

| | |
|---|---|
| **Workstream** | F — Runtime: settings, CLI & scheduler ([plan](../plan/06-runtime.md)) |
| **Depends on** | [T-006](T-006-test-fakes.md) (milestone M0) |
| **Blocks** | [T-602](T-602-cli-skeleton-check.md), [T-605](T-605-scheduler.md) |
| **Size** | S (≤ 1 day) |

## Files

- `src/leaderboard/settings.py`
- `tests/test_settings.py`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [06-runtime.md](../plan/06-runtime.md) §5.1

## Scope

- `Settings.from_env(env)`: defaults per the table, parse booleans and comma lists, `ZoneInfo(TIMEZONE)`, and `Path` fields.
- `require(*names)` helper: raise `SystemExit("Missing SLACK_BOT_TOKEN (see .env.example)")`. It's called per command, not at load.

## Acceptance criteria

- [ ] Defaults, boolean and list parsing, and a bad timezone gives a clear error.
- [ ] A missing required value names the variable.
- [ ] `uv run pytest` passes; PR reviewed and merged
