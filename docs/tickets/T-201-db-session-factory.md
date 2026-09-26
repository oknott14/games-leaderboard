# T-201 · Database session factory

| | |
|---|---|
| **Workstream** | B — Persistence & service ([plan](../plan/02-persistence-service.md)) |
| **Depends on** | [T-006](T-006-test-fakes.md) (milestone M0) |
| **Blocks** | [T-202](T-202-message-ingest.md) |
| **Size** | S (≤ 1 day) |

## Files

- `src/leaderboard/db.py`
- `tests/test_db.py`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [02-persistence-service.md](../plan/02-persistence-service.md) §5.1

## Scope

- `make_session_factory(url)`: create the parent directory for a SQLite file, and on each connect set `foreign_keys=ON`, `journal_mode=WAL` and `busy_timeout=5000`.
- `create_all`, then return `sessionmaker(engine, expire_on_commit=False)`.

## Acceptance criteria

- [x] Creates a missing directory.
- [x] Foreign keys are enforced (a raw SQL delete of a message cascades).
- [x] `PRAGMA journal_mode` returns `wal`.
- [x] `uv run pytest` passes; committed and pushed to `master`
