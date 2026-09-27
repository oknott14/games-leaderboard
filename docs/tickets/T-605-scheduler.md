# T-605 · Scheduled auto-posts

| | |
|---|---|
| **Workstream** | F — Runtime: settings, CLI & scheduler ([plan](../plan/06-runtime.md)) |
| **Depends on** | [T-601](T-601-settings.md), [T-205](T-205-run-query.md), [T-401](T-401-resolve-anchor.md), [T-405](T-405-format-board.md) |
| **Blocks** | [T-604](T-604-cli-run-backfill.md), [T-801](T-801-e2e-test.md) |
| **Size** | S (≤ 1 day) |

## Files

- `src/leaderboard/scheduler.py`
- `tests/test_scheduler.py`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [06-runtime.md](../plan/06-runtime.md) §5.4

## Scope

- `start_scheduler`: returns `None` for an empty schedule. Otherwise a `BackgroundScheduler(tz)` with one cron job per entry, `misfire_grace_time=3600` and `coalesce=True`.
- `run_schedule_entry`: resolve the anchor, format each board, join them, and post once per channel. Skip empty boards, post nothing if all are empty, and log exceptions without raising.

## Acceptance criteria

- [x] With `FakePort`: one combined post per channel, anchored at the Sunday for `last_week`.
- [x] Nothing is posted when all boards are empty.
- [x] An exception is logged.
- [x] An empty schedule gives `None`.
- [x] `uv run pytest` passes; committed and pushed to `master`
