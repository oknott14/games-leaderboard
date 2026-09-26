# T-323 · Command token collision check

| | |
|---|---|
| **Workstream** | C3 — Boards engine: registry, boards.yaml & plugins ([plan](../plan/03-boards-engine.md)) |
| **Depends on** | [T-322](T-322-load-boards.md) |
| **Blocks** | [T-324](T-324-starter-boards-and-plugin.md) |
| **Size** | S (≤ 1 day) |

## Files

- `src/leaderboard/boards/config.py`
- `tests/test_boards_config.py`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [03-boards-engine.md](../plan/03-boards-engine.md) §5.8 step 5
- [04-commands-formatting.md](../plan/04-commands-formatting.md) §5.1

## Scope

- These must all be distinct: board names, game names and aliases, value names, aggregator names, window names, `ANCHOR_WORDS` and `RESERVED_WORDS`. Value names may repeat across games.
- The error names both colliding items and their kinds.

## Acceptance criteria

- [ ] Each kind of collision is detected, and repeated value names across games are allowed.
- [ ] `uv run pytest` passes; committed and pushed to `master`
