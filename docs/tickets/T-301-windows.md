# T-301 · Built-in windows

| | |
|---|---|
| **Workstream** | C1 — Boards engine: windows & aggregators ([plan](../plan/03-boards-engine.md)) |
| **Depends on** | [T-006](T-006-test-fakes.md) (milestone M0) |
| **Blocks** | [T-324](T-324-starter-boards-and-plugin.md) |
| **Size** | S (≤ 1 day) |

## Files

- `src/leaderboard/boards/windows.py`
- `tests/test_windows.py`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [03-boards-engine.md](../plan/03-boards-engine.md) §5.2

## Scope

- Register `day`, `week` (Mon–anchor), `month`, `year`, `all`, `rolling_days(n)` and `last_n(n)` with `@window`, with Pydantic params models (`n: int = Field(ge=1)`) where needed.
- `last_n` returns `DateRange(None, anchor)` plus a `select` that keeps each player's latest `n` entries.

## Acceptance criteria

- [ ] `week` anchored on a Sunday covers Mon–Sun, and anchored on a Monday covers that single day.
- [ ] Month and year starts are correct.
- [ ] `rolling_days: 7` covers exactly 7 days.
- [ ] `last_n: 2` trims each player independently.
- [ ] `uv run pytest` passes; committed and pushed to `master`
