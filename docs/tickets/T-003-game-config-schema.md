# T-003 · Game config schema & parser types

| | |
|---|---|
| **Workstream** | 0 — Contracts & scaffold ([plan](../plan/00-contracts.md)) |
| **Depends on** | [T-001](T-001-project-scaffold.md) |
| **Blocks** | [T-005](T-005-remaining-stubs.md) |
| **Size** | S (≤ 1 day) |

## Files

- `src/leaderboard/config.py` (schema + stubs)
- `src/leaderboard/parser.py` (types + stub)
- `tests/test_contracts_config.py`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [00-contracts.md](../plan/00-contracts.md) §5.2, §5.3
- [01-parsing.md](../plan/01-parsing.md) §5.6 (example YAML)

## Scope

- Pydantic models `NumberSpec`, `ScoreSpec`, `RoundsSpec`, `PuzzleSpec`, `ValueSpec` and `GameConfig`, all with `extra="forbid"` and the exact fields and defaults from the contract.
- Only field-level validation here: the slug regex on `name`. Cross-field rules belong to T-101.
- Method stubs (`label`, `value_names`, `value`, `higher_is_better_for`) and `load_games` raise `NotImplementedError`.
- `parser.py`: the `ParsedResult` dataclass, the `PluginParser` alias, and a stub `parse_message`.

## Out of scope

- Regex compilation and cross-field validation (T-101).

## Acceptance criteria

- [ ] Each example YAML in `01-parsing.md` §5.6 validates via `GameConfig.model_validate(yaml.safe_load(...) | {"name": ...})`.
- [ ] An unknown key is rejected.
- [ ] `ParsedResult` is frozen and its defaults match the contract.
- [ ] `uv run pytest` passes; committed and pushed to `master`
