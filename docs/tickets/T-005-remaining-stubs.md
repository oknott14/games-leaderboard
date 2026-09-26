# T-005 · Remaining module stubs

| | |
|---|---|
| **Workstream** | 0 — Contracts & scaffold ([plan](../plan/00-contracts.md)) |
| **Depends on** | [T-002](T-002-ports-and-models.md), [T-003](T-003-game-config-schema.md), [T-004](T-004-boards-contracts.md) |
| **Blocks** | [T-006](T-006-test-fakes.md) |
| **Size** | S (≤ 1 day) |

## Files

- `src/leaderboard/commands.py`
- `src/leaderboard/formatting.py`
- `src/leaderboard/db.py`
- `src/leaderboard/service.py`
- `src/leaderboard/adapters/slack.py`
- `src/leaderboard/settings.py`
- `src/leaderboard/scheduler.py`
- `src/leaderboard/cli.py`
- `src/leaderboard/__main__.py`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [00-contracts.md](../plan/00-contracts.md) §5.9–§5.13

## Scope

- Create every remaining signature from the contract. Bodies raise `NotImplementedError`.
- `commands.py` includes the finished constants `ANCHOR_WORDS` and `RESERVED_WORDS`, plus the `Query`, `InfoRequest` and `CommandError` dataclasses.
- `settings.py` includes the finished `Settings` dataclass fields. Only `from_env` is stubbed.
- `adapters/slack.py` may import `slack_bolt`. No other module may.
- `__main__.py` calls `cli.main()`.

## Acceptance criteria

- [ ] Every module imports without error.
- [ ] A reviewer has checked every signature against `00-contracts.md`.
- [ ] `grep -r slack_ src/leaderboard` finds matches only in `adapters/`.
- [ ] `uv run pytest` passes; committed and pushed to `master`
