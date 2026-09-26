# T-006 · Shared test fakes & contract smoke tests (milestone M0)

| | |
|---|---|
| **Workstream** | 0 — Contracts & scaffold ([plan](../plan/00-contracts.md)) |
| **Depends on** | [T-005](T-005-remaining-stubs.md) |
| **Blocks** | [T-101](T-101-config-validation.md), [T-201](T-201-db-session-factory.md), [T-301](T-301-windows.md), [T-302](T-302-core-aggregators.md), [T-311](T-311-dedupe-and-rank.md), [T-321](T-321-registry-loading.md), [T-401](T-401-resolve-anchor.md), [T-404](T-404-value-and-range-format.md), [T-501](T-501-slack-normalize.md), [T-601](T-601-settings.md) |
| **Size** | M (1–3 days) |

## Files

- `tests/conftest.py`
- `tests/test_contracts.py`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [00-contracts.md](../plan/00-contracts.md) §6

## Scope

- Build every fixture and helper in contracts §6: `SAMPLES`, `sample_games()`, `make_rows()`, `make_board()`, `FakePort`, `sessions` and `fixed_today` (Thu 2026-09-24).
- `sessions` uses `create_engine` + `create_all` directly with `PRAGMA foreign_keys=ON`, so it doesn't depend on `db.py`.
- `FakePort` records `posted` messages, serves a `history` list filtered by `oldest`, looks up `names`, and has a no-op `run`.
- `test_contracts.py`: every module imports, every contract dataclass can be constructed, and every fixture works.

## Acceptance criteria

- [ ] `uv run pytest` passes.
- [ ] Reviewed by at least one engineer from each of A, B, C and D. **Merging this ticket completes milestone M0** and unblocks all component work.
- [ ] `uv run pytest` passes; PR reviewed and merged

## Notes

- `SAMPLES` starts with best-guess share texts. T-107 replaces them with real ones.
