# T-203 · Reparse all stored messages

| | |
|---|---|
| **Workstream** | B — Persistence & service ([plan](../plan/02-persistence-service.md)) |
| **Depends on** | [T-202](T-202-message-ingest.md) |
| **Blocks** | [T-603](T-603-cli-offline-commands.md), [T-801](T-801-e2e-test.md) |
| **Size** | S (≤ 1 day) |

## Files

- `src/leaderboard/service.py` (`reparse`)
- `tests/test_service.py`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [02-persistence-service.md](../plan/02-persistence-service.md) §5.5

## Scope

- In one transaction: bulk-delete the results, re-parse every message in `posted_at` order, insert the results, and return the count.

## Acceptance criteria

- [x] After swapping in a game config with a different score regex, `reparse` produces the new scores.
- [x] Row counts are stable when it runs twice.
- [x] `uv run pytest` passes; committed and pushed to `master`
