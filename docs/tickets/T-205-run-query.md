# T-205 · run_query: load rows & build BoardResult

| | |
|---|---|
| **Workstream** | B — Persistence & service ([plan](../plan/02-persistence-service.md)) |
| **Depends on** | [T-202](T-202-message-ingest.md) |
| **Blocks** | [T-206](T-206-on-command.md), [T-605](T-605-scheduler.md) |
| **Size** | S (≤ 1 day) |

## Files

- `src/leaderboard/service.py` (`run_query`)
- `tests/test_service.py`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [02-persistence-service.md](../plan/02-persistence-service.md) §5.7
- [00-contracts.md](../plan/00-contracts.md) §5.8

## Scope

- For each game (`query.games` or all, filtered by `board_applies`), build a `load_rows(range)` closure that returns `ResultRow`s with rounds eager-loaded and `start=None` treated as unbounded.
- Call `run_board`, and assemble `BoardResult` with `board_range` and `board_unit`, keeping only non-empty sections.
- Use monkeypatched stand-ins for the engine functions until T-315 merges.

## Acceptance criteria

- [ ] `load_rows` returns only rows in the range, for the right game, with rounds in order.
- [ ] Games that don't apply are skipped.
- [ ] Empty sections are dropped.
- [ ] `uv run pytest` passes; PR reviewed and merged
