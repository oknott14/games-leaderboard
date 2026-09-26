# T-311 · dedupe_daily & competition ranking

| | |
|---|---|
| **Workstream** | C2 — Boards engine: board types & engine ([plan](../plan/03-boards-engine.md)) |
| **Depends on** | [T-006](T-006-test-fakes.md) (milestone M0) |
| **Blocks** | [T-312](T-312-ranked-board-type.md), [T-315](T-315-engine.md) |
| **Size** | S (≤ 1 day) |

## Files

- `src/leaderboard/boards/core.py` (function bodies only)
- `tests/test_core.py`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [03-boards-engine.md](../plan/03-boards-engine.md) §5.4

## Scope

- `dedupe_daily`: one row per `(player, played_on)`. `first` keeps the earliest `posted_at`, `last` the latest, and `best` the best score by direction (ties go to the earliest).
- `rank`: sort by value in the given direction, then by player. Competition ranking 1, 1, 3.

## Acceptance criteria

- [x] Each policy picks the right row, including when rows arrive out of order.
- [x] Ties give 1, 1, 3, and both directions work.
- [x] `uv run pytest` passes; committed and pushed to `master`
