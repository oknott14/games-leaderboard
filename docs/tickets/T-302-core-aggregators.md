# T-302 · Core aggregators

| | |
|---|---|
| **Workstream** | C1 — Boards engine: windows & aggregators ([plan](../plan/03-boards-engine.md)) |
| **Depends on** | [T-006](T-006-test-fakes.md) (milestone M0) |
| **Blocks** | [T-303](T-303-stat-aggregators.md), [T-801](T-801-e2e-test.md) |
| **Size** | S (≤ 1 day) |

## Files

- `src/leaderboard/boards/aggregators.py`
- `tests/test_aggregators.py`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [03-boards-engine.md](../plan/03-boards-engine.md) §5.3

## Scope

- Register `sum`, `avg`, `median`, `best`, `worst`, `max`, `min`, `latest`, `first` and `count` with `@aggregator`.
- `count` has `unit="games"` and `higher_is_better=True`.
- `best` and `worst` use `ctx.higher_is_better`.

## Acceptance criteria

- [ ] Each aggregator is correct on a small list.
- [ ] `best`/`worst` flip with the direction.
- [ ] An empty list gives `None` (except `count`, which gives 0).
- [ ] `uv run pytest` passes; committed and pushed to `master`
