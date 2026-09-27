# T-503 · Slack history fetch with thread replies

| | |
|---|---|
| **Workstream** | E — Slack adapter ([plan](../plan/05-slack-adapter.md)) |
| **Depends on** | [T-502](T-502-slack-port-core.md) |
| **Blocks** | [T-604](T-604-cli-run-backfill.md) |
| **Size** | S (≤ 1 day) |

## Files

- `src/leaderboard/adapters/slack.py` (`fetch_history`)
- `tests/test_slack_adapter.py`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [05-slack-adapter.md](../plan/05-slack-adapter.md) §5.4

## Scope

- Page `conversations.history` (limit 200, cursor). For parents with `reply_count > 0`, page `conversations.replies`, skipping the parent. Yield converted messages.

## Acceptance criteria

- [x] A 2-page stub history plus one thread yields every message once, with no duplicate parents.
- [x] `uv run pytest` passes; committed and pushed to `master`
