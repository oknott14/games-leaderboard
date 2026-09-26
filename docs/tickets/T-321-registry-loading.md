# T-321 · Built-in & plugin loading, params validation

| | |
|---|---|
| **Workstream** | C3 — Boards engine: registry, boards.yaml & plugins ([plan](../plan/03-boards-engine.md)) |
| **Depends on** | [T-006](T-006-test-fakes.md) (milestone M0) |
| **Blocks** | [T-322](T-322-load-boards.md), [T-403](T-403-parse-adhoc.md), [T-602](T-602-cli-skeleton-check.md) |
| **Size** | S (≤ 1 day) |

## Files

- `src/leaderboard/boards/registry.py` (`load_builtins`, `load_plugins`, `validate_params`)
- `tests/test_registry.py`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [03-boards-engine.md](../plan/03-boards-engine.md) §5.7
- T-004 note on `__positional__`

## Scope

- `load_builtins()` imports `windows`, `aggregators` and `types`. Repeat calls do nothing.
- `load_plugins(dir)`: returns `[]` if the directory is missing. Otherwise it adds `dir` to `sys.path`, imports each `*.py` in sorted order (skipping `_*`), and returns the newly registered names. An import error becomes `RuntimeError("plugin <file>: …")`.
- `validate_params(reg, raw)`: with no params model, reject non-empty `raw`. Map `__positional__` to the model's first field, then `model_validate`.

## Acceptance criteria

- [ ] A plugin in `tmp_path` registers.
- [ ] A syntax error names the file.
- [ ] `{last_n: 5}` shorthand validates to `n=5`.
- [ ] Unexpected params on a component that has no params model are rejected.
- [ ] `uv run pytest` passes; PR reviewed and merged
