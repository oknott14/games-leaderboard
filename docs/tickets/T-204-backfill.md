# T-204 · History backfill

| | |
|---|---|
| **Workstream** | B — Persistence & service ([plan](../plan/02-persistence-service.md)) |
| **Depends on** | [T-202](T-202-message-ingest.md) |
| **Blocks** | [T-604](T-604-cli-run-backfill.md), [T-801](T-801-e2e-test.md) |
| **Size** | S (≤ 1 day) |

## Files

- `src/leaderboard/service.py` (`backfill`, `latest_posted_at`)
- `tests/test_service.py`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [02-persistence-service.md](../plan/02-persistence-service.md) §5.6, §5.9

## Scope

- `latest_posted_at` returns an aware UTC datetime or `None`.
- `backfill(port, since=None, default_days=90)`: per channel, use the explicit `since`, else latest minus 1 day, else now minus `default_days`. Feed `port.fetch_history` into `on_message` and return the total processed.

## Acceptance criteria

- [ ] All three `since` rules are covered, using `FakePort`.
- [ ] Replaying the same history twice leaves identical row counts.
- [ ] `uv run pytest` passes; committed and pushed to `master`
