# T-405 · format_board

| | |
|---|---|
| **Workstream** | D — Commands & formatting ([plan](../plan/04-commands-formatting.md)) |
| **Depends on** | [T-404](T-404-value-and-range-format.md) |
| **Blocks** | [T-605](T-605-scheduler.md), [T-801](T-801-e2e-test.md) |
| **Size** | S (≤ 1 day) |

## Files

- `src/leaderboard/formatting.py` (`format_board`)
- `tests/test_formatting.py`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [04-commands-formatting.md](../plan/04-commands-formatting.md) §5.2

## Scope

- Header, then a section per game, truncated to `board.limit`.
- Medals for ranks 1–3 (ties share a medal), then `N.`. Show `· N games` when there's more than 1 entry, and `· detail` when there's a detail.
- An empty result gives `_No results yet._`.

## Acceptance criteria

- [ ] Medal ties, truncation, suffixes and the empty message all match §5.2.
- [ ] `uv run pytest` passes; committed and pushed to `master`
