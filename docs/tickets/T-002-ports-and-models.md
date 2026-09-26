# T-002 · Chat ports & ORM models

| | |
|---|---|
| **Workstream** | 0 — Contracts & scaffold ([plan](../plan/00-contracts.md)) |
| **Depends on** | [T-001](T-001-project-scaffold.md) |
| **Blocks** | [T-005](T-005-remaining-stubs.md) |
| **Size** | S (≤ 1 day) |

## Files

- `src/leaderboard/ports.py`
- `src/leaderboard/models.py`
- `tests/test_models.py`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [00-contracts.md](../plan/00-contracts.md) §5.1, §5.4
- [decisions.md](../plan/decisions.md) #5, #6, #12

## Scope

- `ports.py`: `ChatMessage`, `ChatHandler` and `ChatPort`, exactly as in the contract. They're complete; there's nothing to stub.
- `models.py`: `Base`, `Message`, `GameResult` and `GameRound` with the columns, indexes, unique constraints, FKs (`ON DELETE CASCADE`) and relationships (`cascade="all, delete-orphan"`, rounds ordered by `round_no`) from the contract.
- All datetimes are naive UTC columns (document this in the module docstring).

## Out of scope

- Engine/session setup and pragmas (T-201).

## Acceptance criteria

- [ ] `Base.metadata.create_all` works on a temporary SQLite file.
- [ ] Inserting a duplicate `(platform, channel_id, message_id)` raises `IntegrityError`.
- [ ] Deleting a `Message` through the ORM removes its results and rounds.
- [ ] `GameResult.rounds` comes back ordered by `round_no`.
- [ ] `uv run pytest` passes; PR reviewed and merged
