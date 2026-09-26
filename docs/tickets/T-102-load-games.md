# T-102 · Load game configs from a directory

| | |
|---|---|
| **Workstream** | A — Parsing & game configs ([plan](../plan/01-parsing.md)) |
| **Depends on** | [T-101](T-101-config-validation.md) |
| **Blocks** | [T-107](T-107-starter-games.md), [T-108](T-108-parse-cli.md), [T-602](T-602-cli-skeleton-check.md) |
| **Size** | S (≤ 1 day) |

## Files

- `src/leaderboard/config.py` (`load_games`)
- `tests/test_config.py`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [01-parsing.md](../plan/01-parsing.md) §5.5

## Scope

- Read `*.yaml` and `*.yml` in sorted order, and default `name` to the file stem.
- Drop games with `enabled: false`.
- Reject duplicate names or aliases across files (case-insensitive).
- Re-raise every error as `ValueError(f"{path}: {details}")`.

## Acceptance criteria

- [ ] Loads a temporary directory of valid games and skips the disabled ones.
- [ ] A duplicate alias across two files gives an error naming the second file.
- [ ] A malformed YAML file gives an error naming the file.
- [ ] `uv run pytest` passes; committed and pushed to `master`
