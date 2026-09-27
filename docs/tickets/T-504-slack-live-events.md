# T-504 · Live events, @mentions & /leaderboard

| | |
|---|---|
| **Workstream** | E — Slack adapter ([plan](../plan/05-slack-adapter.md)) |
| **Depends on** | [T-502](T-502-slack-port-core.md) |
| **Blocks** | [T-604](T-604-cli-run-backfill.md) |
| **Size** | M (1–3 days) |

## Files

- `src/leaderboard/adapters/slack.py` (`run` + dispatch helpers)
- `tests/test_slack_adapter.py`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [05-slack-adapter.md](../plan/05-slack-adapter.md) §5.5

## Scope

- Plain `message` events call `on_message`, `message_changed` calls `on_message` with the nested message, and `message_deleted` calls `on_message_deleted`.
- `app_mention`: strip `<@bot>`, call `on_command`, and reply in a thread.
- `/leaderboard`: `ack()` first, then `on_command`, then `respond(in_channel)`.
- Every handler catches and logs exceptions. Put the dispatch logic in plain functions so it can be tested without Bolt networking.

## Acceptance criteria

- [x] Every item in the `05-slack-adapter.md` §7 event, mention, slash-command and exception list.
- [x] `uv run pytest` passes; committed and pushed to `master`
