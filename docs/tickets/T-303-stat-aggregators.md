# T-303 · Statistical aggregators: stddev, streak, top_k_avg

| | |
|---|---|
| **Workstream** | C1 — Boards engine: windows & aggregators ([plan](../plan/03-boards-engine.md)) |
| **Depends on** | [T-302](T-302-core-aggregators.md) |
| **Blocks** | [T-324](T-324-starter-boards-and-plugin.md) |
| **Size** | S (≤ 1 day) |

## Files

- `src/leaderboard/boards/aggregators.py`
- `tests/test_aggregators.py`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [03-boards-engine.md](../plan/03-boards-engine.md) §5.3

## Scope

- `stddev`: population standard deviation, `None` with fewer than 2 entries, and `higher_is_better=False`.
- `streak`: consecutive played days ending at the most recent played day. It's 0 unless that day is the anchor or the day before. `unit="days"`, `higher_is_better=True`.
- `top_k_avg(k)`: the mean of the best `k` values by direction.

## Acceptance criteria

- [ ] A gap resets `streak`, and a streak ending 2 or more days before the anchor is 0.
- [ ] `stddev` returns `None` for a single entry.
- [ ] `top_k_avg` respects the direction and `k`.
- [ ] `uv run pytest` passes; PR reviewed and merged

## Notes

- This edits the same file as T-302, so it goes after it (ideally the same engineer).
