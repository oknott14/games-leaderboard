# T-401 · Anchor resolution

| | |
|---|---|
| **Workstream** | D — Commands & formatting ([plan](../plan/04-commands-formatting.md)) |
| **Depends on** | [T-006](T-006-test-fakes.md) (milestone M0) |
| **Blocks** | [T-402](T-402-parse-saved-boards.md), [T-605](T-605-scheduler.md) |
| **Size** | S (≤ 1 day) |

## Files

- `src/leaderboard/commands.py` (`resolve_anchor`)
- `tests/test_commands.py`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [04-commands-formatting.md](../plan/04-commands-formatting.md) §5.1 (resolve_anchor table)

## Scope

- Handle `today`, `yesterday`, `lastweek`/`last_week` (the previous week's Sunday), `lastmonth`/`last_month` (the last day of the previous month) and `YYYY-MM-DD`. Anything else gives `None`.

## Acceptance criteria

- [x] Every row of the table is covered, including across month and year boundaries.
- [x] `uv run pytest` passes; committed and pushed to `master`

## Notes

- The scheduler (T-605) uses this too.
