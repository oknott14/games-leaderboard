# T-206 · on_command dispatch & error fallback

| | |
|---|---|
| **Workstream** | B — Persistence & service ([plan](../plan/02-persistence-service.md)) |
| **Depends on** | [T-205](T-205-run-query.md) |
| **Blocks** | [T-603](T-603-cli-offline-commands.md), [T-801](T-801-e2e-test.md) |
| **Size** | S (≤ 1 day) |

## Files

- `src/leaderboard/service.py` (`on_command`)
- `tests/test_service.py`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [02-persistence-service.md](../plan/02-persistence-service.md) §5.8

## Scope

- `parse_command` routes to `format_board(run_query(...))`, `format_info(...)` or `format_error(...)`.
- Any exception is logged with its traceback, and the reply is `"Sorry, something went wrong — check the bot logs."`.
- Use stand-ins for D's functions until T-402 and T-405 merge.

## Acceptance criteria

- [ ] Each of the three result kinds routes correctly.
- [ ] An exception gives the fallback reply and a logged traceback.
- [ ] `uv run pytest` passes; PR reviewed and merged
