# T-106 · Plugin parser escape hatch

| | |
|---|---|
| **Workstream** | A — Parsing & game configs ([plan](../plan/01-parsing.md)) |
| **Depends on** | [T-103](T-103-parse-message.md) |
| **Blocks** | — |
| **Size** | S (≤ 1 day) |

## Files

- `src/leaderboard/parser.py`
- `tests/test_parser.py`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [01-parsing.md](../plan/01-parsing.md) §5.1 (plugin escape hatch)
- [00-contracts.md](../plan/00-contracts.md) §5.3

## Scope

- If `game.parser` is set, resolve `module:function` lazily (and cache it), call it with the text, and set `game` on the result with `dataclasses.replace`.
- Assume the plugin directory is already on `sys.path` (T-321 adds it). In tests, use `monkeypatch.syspath_prepend`.
- An import or attribute error gives a clear `ValueError` naming the game and the `parser` string.

## Acceptance criteria

- [ ] A plugin in `tmp_path` is called, and its result's `game` is overridden.
- [ ] A plugin returning `None` gives no result.
- [ ] A bad `module:function` gives a clear error.
- [ ] `uv run pytest` passes; PR reviewed and merged
