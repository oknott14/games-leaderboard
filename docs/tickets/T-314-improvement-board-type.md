# T-314 · `improvement` board type

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

- The previous range is the same length, immediately before the current one. Get it via `ctx.fetch`.
- `delta = agg(current) − agg(previous)`, negated when lower is better. Keep only players present in both periods.
- `unit="±"`, and `detail="{prev} → {cur}"`. An unbounded range raises `ValueError`.

## Acceptance criteria

- [ ] Positive always means improved, in both directions.
- [ ] Players missing from either period are excluded.
- [ ] An unbounded window raises.
- [ ] `uv run pytest` passes; committed and pushed to `master`

## Notes

- This touches the same file as T-313. They can run in parallel, but expect a trivial merge.
