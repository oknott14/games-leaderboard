# T-202 · Message ingest: upsert, edit, delete

| | |
|---|---|
| **Workstream** | B — Persistence & service ([plan](../plan/02-persistence-service.md)) |
| **Depends on** | [T-201](T-201-db-session-factory.md) |
| **Blocks** | [T-203](T-203-reparse.md), [T-204](T-204-backfill.md), [T-205](T-205-run-query.md) |
| **Size** | M (1–3 days) |

## Files

- `src/leaderboard/service.py` (`__init__`, time helpers, `on_message`, `on_message_deleted`)
- `tests/test_service.py`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [02-persistence-service.md](../plan/02-persistence-service.md) §5.2–§5.4

## Scope

- Time helpers: `to_db` (aware → naive UTC), `from_db`, and `local_date(dt, tz)`.
- `on_message`:
  - apply the channel filter, then parse
  - upsert by `(platform, channel_id, message_id)`, setting `edited_at` only when the text changed
  - replace the message's results and rounds
  - respect `store_non_game`
- `on_message_deleted` deletes the message (the cascade does the rest).
- Use a monkeypatched stand-in for `parse_message` (e.g. it matches `TEST <n>`) until T-103 merges.

## Acceptance criteria

- [ ] Every ingest, edit, delete, channel-filter, timezone-boundary and `store_non_game` case in `02-persistence-service.md` §7.
- [ ] `uv run pytest` passes; committed and pushed to `master`
