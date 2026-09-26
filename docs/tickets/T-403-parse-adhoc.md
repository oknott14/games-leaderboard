# T-403 · Command parsing: ad-hoc boards, params & suggestions

| | |
|---|---|
| **Workstream** | D — Commands & formatting ([plan](../plan/04-commands-formatting.md)) |
| **Depends on** | [T-402](T-402-parse-saved-boards.md), [T-321](T-321-registry-loading.md) |
| **Blocks** | [T-801](T-801-e2e-test.md) |
| **Size** | M (1–3 days) |

## Files

- `src/leaderboard/commands.py`
- `tests/test_commands.py`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [04-commands-formatting.md](../plan/04-commands-formatting.md) §5.1 (rules 3, 6, `name=value`)

## Scope

- Tokens for values, aggregators and windows (read from the registries) build an ad-hoc `ranked` board, with defaults of value `score`, window `week` and aggregate `best`, and an auto-generated title.
- `name=value` params attach to the named component, or to the only ad-hoc component with that field. Validate them with `validate_params`, and turn errors into a `CommandError`.
- Mixing a saved board with ad-hoc parts gives an error.
- Suggestions come from `difflib.get_close_matches(n=3, cutoff=0.6)`.

## Acceptance criteria

- [ ] The ad-hoc, params, mixing-error and `wekly`-suggestion cases in `04-commands-formatting.md` §7.
- [ ] `uv run pytest` passes; PR reviewed and merged

## Notes

- Tests register stand-in aggregators and windows with the decorators.
