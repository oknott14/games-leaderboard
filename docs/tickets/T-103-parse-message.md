# T-103 · parse_message: detect, score, puzzle, multi-game

| | |
|---|---|
| **Workstream** | A — Parsing & game configs ([plan](../plan/01-parsing.md)) |
| **Depends on** | [T-101](T-101-config-validation.md) |
| **Blocks** | [T-104](T-104-rounds-extraction.md), [T-106](T-106-plugin-parser.md), [T-108](T-108-parse-cli.md) |
| **Size** | M (1–3 days) |

## Files

- `src/leaderboard/parser.py`
- `tests/test_parser.py`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [01-parsing.md](../plan/01-parsing.md) §5.1 (steps 1, 2, 4), §5.3

## Scope

- For each game: run `detect`, then the `score.pattern` extraction via `parse_number`, then the optional `puzzle`.
- If `detect` matches but the score fails, log a warning (game name + the first 80 characters) and skip the game.
- Return results for **every** matching game, in input order.
- It's a pure function: no I/O except logging.

## Out of scope

- Rounds and `from_rounds` totals (T-104), the plugin hook (T-106).

## Acceptance criteria

- [ ] TimeGuessr `TimeGuessr #512 38,532/50,000` gives score 38532 and puzzle `"512"`.
- [ ] Two games in one message give two results.
- [ ] A non-game message gives `[]`.
- [ ] `detect` matching with the score missing gives `[]` plus a warning (`caplog`).
- [ ] `uv run pytest` passes; committed and pushed to `master`
