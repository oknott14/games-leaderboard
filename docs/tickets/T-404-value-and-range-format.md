# T-404 · Value & date-range formatting

| | |
|---|---|
| **Workstream** | D — Commands & formatting ([plan](../plan/04-commands-formatting.md)) |
| **Depends on** | [T-006](T-006-test-fakes.md) (milestone M0) |
| **Blocks** | [T-405](T-405-format-board.md), [T-406](T-406-format-info-error.md) |
| **Size** | S (≤ 1 day) |

## Files

- `src/leaderboard/formatting.py` (`fmt_value`, range helper)
- `tests/test_formatting.py`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [04-commands-formatting.md](../plan/04-commands-formatting.md) §5.2

## Scope

- `fmt_value`: integer values with thousands separators, otherwise one decimal. `±` always shows a sign. Other units are appended (`5 days`).
- Range formatting: a single day (`Tue Sep 23`), the same month (`Sep 15–21`), across months (`Aug 28 – Sep 3`), and all time (`all time to Sep 24`).

## Acceptance criteria

- [ ] Every example in §5.2 is covered.
- [ ] `uv run pytest` passes; PR reviewed and merged
