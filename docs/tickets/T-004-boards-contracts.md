# T-004 · Boards engine contracts & plugin decorators

| | |
|---|---|
| **Workstream** | 0 — Contracts & scaffold ([plan](../plan/00-contracts.md)) |
| **Depends on** | [T-001](T-001-project-scaffold.md) |
| **Blocks** | [T-005](T-005-remaining-stubs.md) |
| **Size** | M (1–3 days) |

## Files

- `src/leaderboard/boards/__init__.py`
- `src/leaderboard/boards/core.py` (types + stubs)
- `src/leaderboard/boards/registry.py` (decorators complete; loaders stubbed)
- `src/leaderboard/boards/config.py` (schema + stub loader)
- `src/leaderboard/boards/engine.py` (types + stubs)
- `tests/test_contracts_boards.py`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [00-contracts.md](../plan/00-contracts.md) §5.5–§5.8
- [03-boards-engine.md](../plan/03-boards-engine.md) §5.8 (component shorthand)

## Scope

- `core.py`: the `PlayerKey`, `ResultRow`, `DateRange`, `Entry`, `Standing`, `WindowResult`, `AggContext` and `BoardContext` types. `dedupe_daily` and `rank` are stubs.
- `registry.py`: implement `Registered`, the `WINDOWS`/`AGGREGATORS`/`BOARD_TYPES` dicts, and the `@window`/`@aggregator`/`@board_type` decorators fully. Registering a duplicate name raises `ValueError`. `load_builtins`, `load_plugins` and `validate_params` are stubs.
- `boards/config.py`: `ComponentRef`, with a before-validator that normalises `"avg"`, `{name: x, k: 3}` and `{x: {k: 3}}`. A scalar shorthand `{last_n: 5}` becomes `params={"__positional__": 5}`; T-321 maps it to the first params field. Also `BoardConfig`, `ScheduleEntry` and `BoardsFile`, plus a stub `load_boards`.
- `engine.py`: the `GameBoardResult` and `BoardResult` dataclasses, and stubs for `board_applies`, `board_range`, `board_unit` and `run_board`.
- `boards/__init__.py` re-exports the public plugin API listed in contracts §5.6.
- Import `GameConfig` under `TYPE_CHECKING` only, so this ticket doesn't depend on T-003.

## Out of scope

- Registry loading and reference validation (T-321, T-322).

## Acceptance criteria

- [ ] The decorators register a function and reject a duplicate name.
- [ ] All four `ComponentRef` input forms normalise as specified.
- [ ] The starter `boards.yaml` from `03-boards-engine.md` §5.8 validates as a `BoardsFile` (schema only, no reference checks).
- [ ] `uv run pytest` passes; committed and pushed to `master`
