# T-101 · Game config validation & number parsing

| | |
|---|---|
| **Workstream** | A — Parsing & game configs ([plan](../plan/01-parsing.md)) |
| **Depends on** | [T-006](T-006-test-fakes.md) (milestone M0) |
| **Blocks** | [T-102](T-102-load-games.md), [T-103](T-103-parse-message.md), [T-105](T-105-derived-values.md) |
| **Size** | S (≤ 1 day) |

## Files

- `src/leaderboard/config.py` (validators, `parse_number`)
- `tests/test_config.py`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [01-parsing.md](../plan/01-parsing.md) §5.2, §5.5

## Scope

- `parse_number(raw, spec) -> float | None`: strip, apply `map`, remove `,` `_` and spaces, convert by `type`, and return `None` on failure.
- Model validators:
  - patterns compile with the game's flags
  - `value` and `block` named groups are present
  - `score` has exactly one of `pattern` or `from_rounds`
  - `from_rounds` (on the score or a value) requires `rounds`
  - either `parser`, or both `detect` and `score`
  - `score` is reserved as a value name, and value names are slugs
- Cache compiled regexes (e.g. `functools.cached_property`) for T-103 and T-104 to use.

## Acceptance criteria

- [ ] `parse_number` handles `"38,532"`, `" 7 "`, map `X→7`, the float type, and garbage (→ `None`).
- [ ] Each invalid-config case in `01-parsing.md` §7 (except the cross-file ones) is rejected with a message naming the field.
- [ ] `uv run pytest` passes; committed and pushed to `master`
