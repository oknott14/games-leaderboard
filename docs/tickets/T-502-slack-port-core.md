# T-502 · SlackPort construction, post & display names

| | |
|---|---|
| **Workstream** | E — Slack adapter ([plan](../plan/05-slack-adapter.md)) |
| **Depends on** | [T-501](T-501-slack-normalize.md) |
| **Blocks** | [T-503](T-503-slack-history.md), [T-504](T-504-slack-live-events.md) |
| **Size** | S (≤ 1 day) |

## Files

- `src/leaderboard/adapters/slack.py`
- `tests/test_slack_adapter.py`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [05-slack-adapter.md](../plan/05-slack-adapter.md) §5.1, §5.6

## Scope

- The constructor: a `WebClient` with `proxy` and `ssl`, a `RateLimitErrorRetryHandler(max_retry_count=5)`, and `auth.test` storing `bot_user_id` and logging `Slack auth OK: …`. Fail with a clear message.
- `post` calls `chat.postMessage`. `display_name` falls back display name → real name → name → id, is cached, and never raises.

## Acceptance criteria

- [ ] Tested with a stub client: the fallback order, caching, the id on an API error, and the retry handler attached.
- [ ] `uv run pytest` passes; PR reviewed and merged
