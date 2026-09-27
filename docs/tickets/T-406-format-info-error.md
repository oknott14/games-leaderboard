# T-406 · format_info (help/games/boards) & format_error

| | |
|---|---|
| **Workstream** | D — Commands & formatting ([plan](../plan/04-commands-formatting.md)) |
| **Depends on** | [T-404](T-404-value-and-range-format.md) |
| **Blocks** | [T-801](T-801-e2e-test.md) |
| **Size** | S (≤ 1 day) |

## Files

- `src/leaderboard/formatting.py` (`format_info`, `format_error`)
- `tests/test_formatting.py`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [04-commands-formatting.md](../plan/04-commands-formatting.md) §5.2

## Scope

- `help`: the grammar plus 6–8 examples. `games`: labels, aliases and values. `boards`: saved boards with their compositions, plus the registered windows, aggregators and types with descriptions and params.
- `format_error`: the message, `Did you mean: …?` and `Try \`help\`.`.

## Acceptance criteria

- [x] `boards` output includes a plugin-registered aggregator.
- [x] The error text includes the suggestions.
- [x] `uv run pytest` passes; committed and pushed to `master`

## Notes

- This touches the same file as T-405. They can run in parallel, but expect a trivial merge.
