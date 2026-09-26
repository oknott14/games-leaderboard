# T-105 · Derived values API on GameConfig

| | |
|---|---|
| **Workstream** | A — Parsing & game configs ([plan](../plan/01-parsing.md)) |
| **Depends on** | [T-101](T-101-config-validation.md) |
| **Blocks** | [T-107](T-107-starter-games.md) |
| **Size** | S (≤ 1 day) |

## Files

- `src/leaderboard/config.py` (methods)
- `tests/test_config.py`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [01-parsing.md](../plan/01-parsing.md) §5.4
- [00-contracts.md](../plan/00-contracts.md) §5.2

## Scope

- `label` is `display_name` or `name`. `value_names()` is `["score", *values]`.
- `value(name, score, rounds)`: `score` returns the score. A declared value applies its reducer (`sum`, `avg`, `max`, `min`), or returns `None` when there are no rounds. An unknown name raises `KeyError`.
- `higher_is_better_for(name)` returns the value's override, else the game default.

## Acceptance criteria

- [x] `best_round`, `round_avg` and `worst_round` are correct. They're `None` with no rounds. An unknown value raises `KeyError`. The direction override works.
- [x] `uv run pytest` passes; committed and pushed to `master`

## Notes

- The boards engine (T-315) depends on this API, so keep the signatures exact.
