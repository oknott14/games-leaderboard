# T-322 · boards.yaml loader & reference validation

| | |
|---|---|
| **Workstream** | C3 — Boards engine: registry, boards.yaml & plugins ([plan](../plan/03-boards-engine.md)) |
| **Depends on** | [T-321](T-321-registry-loading.md) |
| **Blocks** | [T-323](T-323-token-collisions.md), [T-324](T-324-starter-boards-and-plugin.md), [T-602](T-602-cli-skeleton-check.md) |
| **Size** | M (1–3 days) |

## Files

- `src/leaderboard/boards/config.py` (`load_boards`)
- `tests/test_boards_config.py`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [03-boards-engine.md](../plan/03-boards-engine.md) §5.8 (validation steps 1–4)

## Scope

- Merge `defaults` under each board, and set `name` from the key.
- Validate the type, window and aggregator names and their params against the registries.
- `value` must exist in some game (or in every listed game), and listed games must exist.
- Schedule boards must exist, and each cron must parse (`CronTrigger.from_crontab`).
- A missing file gives an empty `BoardsFile` plus a warning. Errors read `boards.yaml: board '<name>': …`.

## Acceptance criteria

- [ ] Each rejection case is covered (unknown type, window, aggregator, value or game; bad params; unknown schedule board; bad cron).
- [ ] `defaults` are merged.
- [ ] `uv run pytest` passes; PR reviewed and merged

## Notes

- Tests register stand-in components, so this doesn't wait for C1 or C2.
