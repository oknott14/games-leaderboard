# T-104 · Per-round extraction & from_rounds totals

| | |
|---|---|
| **Workstream** | A — Parsing & game configs ([plan](../plan/01-parsing.md)) |
| **Depends on** | [T-103](T-103-parse-message.md) |
| **Blocks** | [T-107](T-107-starter-games.md) |
| **Size** | M (1–3 days) |

## Files

- `src/leaderboard/parser.py`
- `tests/test_parser.py`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [01-parsing.md](../plan/01-parsing.md) §5.1 step 3 (horizontal and vertical table)

## Scope

- `block` search, then `findall` of `item` **inside the block only** (the single group, or the whole match), converted via `parse_number` using the rounds spec's `map` and `type`.
- `score.from_rounds`: compute the total from the rounds, and skip the game if there are no rounds.
- Put the rounds into `ParsedResult.rounds`.
- `rounds.check_sum`: when true and the score came from `score.pattern`, log a warning if `sum(rounds) != score`. Still record the posted score.

## Acceptance criteria

- [x] MapTap sample gives rounds `(93, 88, 71, 97, 85)`. The date and the total aren't included.
- [x] A test-defined vertical game (one round per line, `MULTILINE`) extracts every line.
- [x] `from_rounds: sum` gives the correct total.
- [x] Krillion tiles (`🏮🌟🐟🏮🏮🦑🦑`, and the same as `:izakaya_lantern::star2:…`) give `(85, 100, 30, 85, 85, 60, 60)` via `map`.
- [x] `check_sum`: a mismatched total logs a warning (`caplog`), a matching one logs nothing, and the posted score is kept either way.
- [x] `uv run pytest` passes; committed and pushed to `master`

## Notes

- Also added `reduce_rounds` to `src/leaderboard/config.py` (outside this ticket's file list), so T-105's derived values share the same reducers. Flagged in the review after T-105.
