# T-602 · CLI skeleton, load_all & `check`

| | |
|---|---|
| **Workstream** | F — Runtime: settings, CLI & scheduler ([plan](../plan/06-runtime.md)) |
| **Depends on** | [T-601](T-601-settings.md), [T-102](T-102-load-games.md), [T-322](T-322-load-boards.md), [T-321](T-321-registry-loading.md) |
| **Blocks** | [T-603](T-603-cli-offline-commands.md), [T-604](T-604-cli-run-backfill.md) |
| **Size** | S (≤ 1 day) |

## Files

- `src/leaderboard/cli.py`
- `tests/test_cli.py`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [06-runtime.md](../plan/06-runtime.md) §5.2, §5.3 (`check`)

## Scope

- argparse with subcommands and `--log-level`, plus logging setup.
- `load_all(settings)`: built-ins, then plugins, then games, then boards. Any error prints and exits 2.
- `check`: print the games and values, the boards and their compositions, the registries (plugins marked) and the schedule.

## Acceptance criteria

- [ ] `check` passes on a fixture config directory, and exits 2 with the file name on broken YAML.
- [ ] `uv run pytest` passes; committed and pushed to `master`
