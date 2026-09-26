# T-312 · `ranked` board type

| | |
|---|---|
| **Workstream** | C2 — Boards engine: board types & engine ([plan](../plan/03-boards-engine.md)) |
| **Depends on** | [T-311](T-311-dedupe-and-rank.md) |
| **Blocks** | [T-313](T-313-daily-wins-board-type.md), [T-314](T-314-improvement-board-type.md), [T-324](T-324-starter-boards-and-plugin.md) |
| **Size** | S (≤ 1 day) |

## Files

- `src/leaderboard/boards/types.py`
- `tests/test_board_types.py`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [03-boards-engine.md](../plan/03-boards-engine.md) §5.5

## Scope

- Register `ranked` with `@board_type`: group `ctx.entries` by player, then `ctx.aggregate`. Drop players with `None` or fewer than `min_entries` entries, then `rank` using `ctx.higher_is_better`.
- Tests build a `BoardContext` by hand, with a simple aggregate lambda.

## Acceptance criteria

- [x] `min_entries` is applied.
- [x] Players whose aggregate is `None` are dropped.
- [x] The direction is respected.
- [x] `uv run pytest` passes; committed and pushed to `master`
