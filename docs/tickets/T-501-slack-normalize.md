# T-501 · Slack text normalisation & message conversion

| | |
|---|---|
| **Workstream** | E — Slack adapter ([plan](../plan/05-slack-adapter.md)) |
| **Depends on** | [T-006](T-006-test-fakes.md) (milestone M0) |
| **Blocks** | [T-502](T-502-slack-port-core.md) |
| **Size** | S (≤ 1 day) |

## Files

- `src/leaderboard/adapters/slack.py` (`normalize_text`, `_to_message`)
- `tests/test_slack_adapter.py`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [05-slack-adapter.md](../plan/05-slack-adapter.md) §5.2, §5.3

## Scope

- `normalize_text`: link, channel and special-mention forms become plain text, user mentions are kept, and entities are unescaped **after** the link substitution.
- `_to_message`: filter subtypes, require `user` and `ts`, `posted_at` is aware UTC, and `thread_id` is set only for replies.

## Acceptance criteria

- [x] Every row of the §5.2 table is covered, and the kept and dropped subtypes of §5.3 behave correctly.
- [x] `uv run pytest` passes; committed and pushed to `master`
