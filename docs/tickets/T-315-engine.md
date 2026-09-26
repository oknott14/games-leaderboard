# T-315 · Board engine: run_board, applies, range, unit

| | |
|---|---|
| **Workstream** | C2 — Boards engine: board types & engine ([plan](../plan/03-boards-engine.md)) |
| **Depends on** | [T-311](T-311-dedupe-and-rank.md) |
| **Blocks** | [T-801](T-801-e2e-test.md) |
| **Size** | M (1–3 days) |

## Files

- `src/leaderboard/boards/engine.py`
- `tests/test_engine.py`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [03-boards-engine.md](../plan/03-boards-engine.md) §5.6

## Scope

- Implement the `run_board` pipeline exactly as in §5.6:
  - window, then `load_rows`, then `dedupe_daily` on the score
  - build values into `Entry`s, sort them, apply the window's `select`
  - resolve the direction (board, then aggregator, then value) and bind the aggregate and `fetch`
  - dispatch to the board type
- `board_applies`, `board_range` and `board_unit` as specified.
- Tests register **stand-in** windows, aggregators and types with unique test names, so this doesn't wait for C1. Use `sample_games` and `make_rows`.

## Acceptance criteria

- [x] `best_round` comes from the post dedupe chose.
- [x] A game without the board's value doesn't apply.
- [x] Direction precedence: the board beats the aggregator, which beats the value.
- [x] `fetch` runs the same pipeline for another range.
- [x] All standings are returned (no truncation).
- [x] `uv run pytest` passes; committed and pushed to `master`

## Notes

- Calls `validate_params` (T-321). Until it merges, monkeypatch it in tests.
