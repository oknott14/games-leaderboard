# T-324 · Starter boards.yaml & example plugin

| | |
|---|---|
| **Workstream** | C3 — Boards engine: registry, boards.yaml & plugins ([plan](../plan/03-boards-engine.md)) |
| **Depends on** | [T-322](T-322-load-boards.md), [T-323](T-323-token-collisions.md), [T-301](T-301-windows.md), [T-303](T-303-stat-aggregators.md), [T-312](T-312-ranked-board-type.md), [T-313](T-313-daily-wins-board-type.md), [T-314](T-314-improvement-board-type.md) |
| **Blocks** | [T-704](T-704-user-readme.md), [T-801](T-801-e2e-test.md) |
| **Size** | S (≤ 1 day) |
| **Needs** | Input or action from the project owner |

## Files

- `boards.yaml`
- `plugins/example_top3_avg.py`
- `tests/test_starter_boards.py`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [03-boards-engine.md](../plan/03-boards-engine.md) §5.8, §5.9

## Scope

- Write `boards.yaml` exactly as in §5.8. Confirm the board list and the schedule with the project owner (open question in the plan doc).
- Write the example plugin with tutorial-quality comments.
- Test: with the real built-ins and the plugin loaded, the starter file validates against `sample_games`, and a board using `top3_avg` validates.

## Acceptance criteria

- [ ] The starter `boards.yaml` and the example plugin load cleanly with the real registries.
- [ ] `uv run pytest` passes; committed and pushed to `master`
