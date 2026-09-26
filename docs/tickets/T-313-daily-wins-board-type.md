# T-313 · `daily_wins` board type

| | |
|---|---|
| **Workstream** | C2 — Boards engine: board types & engine ([plan](../plan/03-boards-engine.md)) |
| **Depends on** | [T-312](T-312-ranked-board-type.md) |
| **Blocks** | [T-324](T-324-starter-boards-and-plugin.md) |
| **Size** | S (≤ 1 day) |

## Files

- `src/leaderboard/boards/types.py`
- `tests/test_board_types.py`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [03-boards-engine.md](../plan/03-boards-engine.md) §5.5

## Scope

- For each day the best value wins, and **ties all win**. Count wins per player, keep players with at least `min_entries` days played, and rank higher-is-better.
- `unit="wins"`, and `detail="{days} played"`.

## Acceptance criteria

- [x] A tied day credits both players.
- [x] Lower-is-better games pick the minimum.
- [x] `detail` is correct.
- [x] `uv run pytest` passes; committed and pushed to `master`
