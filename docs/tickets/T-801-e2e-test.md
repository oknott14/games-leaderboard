# T-801 · Automated end-to-end test

| | |
|---|---|
| **Workstream** | H — Integration & verification ([plan](../plan/08-integration.md)) |
| **Depends on** | [T-107](T-107-starter-games.md), [T-203](T-203-reparse.md), [T-204](T-204-backfill.md), [T-206](T-206-on-command.md), [T-315](T-315-engine.md), [T-324](T-324-starter-boards-and-plugin.md), [T-403](T-403-parse-adhoc.md), [T-405](T-405-format-board.md), [T-406](T-406-format-info-error.md), [T-605](T-605-scheduler.md), [T-302](T-302-core-aggregators.md) |
| **Blocks** | [T-802](T-802-manual-slack-verification.md) |
| **Size** | M (1–3 days) |

## Files

- `tests/test_e2e.py`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [08-integration.md](../plan/08-integration.md) §5

## Scope

- Use the real games, `boards.yaml`, built-ins and example plugin, with a temporary SQLite file and `FakePort`, following the 6 steps in `08-integration.md` §5.
- Assert that the expected leaders and the key text appear. Avoid full snapshots.

## Acceptance criteria

- [ ] `tests/test_e2e.py` passes in CI or locally without the network.
- [ ] `uv run pytest` passes; committed and pushed to `master`
