# Workstream E — Slack Adapter

## 1. Goal

Implement `ChatPort` for Slack using Bolt for Python in **Socket Mode**, so the bot runs on a
laptop with no public URL. It translates Slack events into platform-neutral `ChatMessage`s and
handler calls, and it's the **only** module that imports `slack_bolt` or `slack_sdk`.

## 2. Owns

- `src/leaderboard/adapters/__init__.py`, `src/leaderboard/adapters/slack.py`
- `slack-manifest.yaml`
- `tests/test_slack_adapter.py`

**Must not edit:** anything in the core. If the adapter needs something from the core, that's a
contract change.

## 3. Depends on

[Contracts](00-contracts.md) §5.1 ports, §5.12 this workstream's signatures, and §6 fakes (a fake
`ChatHandler` that records calls).

## 4. Provides

- `SlackPort`, used by F.
- `normalize_text`, used by A's `parse` CLI.

---

## 5. Design

### 5.1 Construction

`SlackPort(bot_token, app_token, *, proxy=None, ssl_context=None)`:
- `App(client=WebClient(token=bot_token, proxy=proxy, ssl=ssl_context))`
- Attaches `RateLimitErrorRetryHandler(max_retry_count=5)` to the client's `retry_handlers`, so a
  429 response backs off and retries automatically.
- Calls `auth.test` once, stores `bot_user_id`, and logs `"Slack auth OK: <team> as <bot>"`. A
  failure raises with a clear message (a bad token, or a network/proxy problem; see
  [07-ops-setup.md](07-ops-setup.md)).
- `platform = "slack"`.

### 5.2 `normalize_text(text)`

Slack sends formatted text. The core expects plain text.

| Slack text | Normalised |
|---|---|
| `<http://www.maptap.gg\|www.maptap.gg>` | `www.maptap.gg` (the label) |
| `<https://example.com>` | `https://example.com` |
| `<mailto:a@b.c\|a@b.c>` | `a@b.c` |
| `<#C123\|general>` | `#general` |
| `<@U123>` | **unchanged** (mentions are kept) |
| `<!here>` | `@here` |
| `&amp;` `&lt;` `&gt;` | `&` `<` `>` (unescaped **after** the link substitution) |

Emoji stay as `:shortcode:` text. Game configs are written against that form (see [01-parsing.md](01-parsing.md)).

### 5.3 `_to_message(channel_id, raw) -> ChatMessage | None`

- Keeps events with no subtype, and the subtypes `thread_broadcast`, `file_share` and `me_message`.
- Drops everything else: `bot_message`, events with a `bot_id`, `channel_join`, `channel_leave`,
  `channel_topic`, `channel_purpose`, `pinned_item`, and so on.
- Requires `user` and `ts`.
- `message_id = ts`, `posted_at = datetime.fromtimestamp(float(ts), UTC)`, `thread_id = thread_ts`
  when it differs from `ts`, and `text = normalize_text(raw.get("text", ""))`.

### 5.4 `fetch_history(channel_id, oldest)`

- Pages `conversations.history(channel, oldest=<epoch>, limit=200, cursor=…)`.
- For each message, yields `_to_message(...)` when it isn't `None`.
- For each message with `reply_count > 0`, also pages `conversations.replies(channel, ts=parent_ts, oldest=…)`
  and yields the replies, skipping the parent itself.
- Order doesn't matter, because ingest is idempotent (B).
- Known limitation: a new reply in an old thread whose parent is older than `oldest` is missed by
  backfill. Live events still capture it while the bot is running.

### 5.5 `run(handler)`

Registers the handlers, then `SocketModeHandler(app, app_token, proxy=…).start()`, which blocks.

| Slack event | Action |
|---|---|
| `message` (no subtype, or a kept subtype) | `handler.on_message(_to_message(event["channel"], event))` |
| `message` / `message_changed` | `handler.on_message(_to_message(channel, event["message"]))`, which re-parses the edit. If the edited message no longer maps to a person's message (e.g. a thread parent deleted while it has replies becomes a `tombstone`), `on_message_deleted` instead. |
| `message` / `message_deleted` | `handler.on_message_deleted("slack", channel, event["deleted_ts"])` |
| `app_mention` | Strip `<@bot_user_id>`. `reply = handler.on_command(text)`. Then `chat.postMessage(channel, reply, thread_ts=event["ts"])` (reply **in a thread**). |
| `/leaderboard` command | `ack()` immediately, then `reply = handler.on_command(command["text"])`, then `respond(text=reply, response_type="in_channel")` |

- The same text arrives as both an `app_mention` and a `message` event. That's fine: the message
  is stored, and the command is answered once.
- Every handler wraps its call in a try/except that logs the exception, so one bad event never
  kills the socket.
- The slash command must `ack()` within 3 seconds. The handler call is fast (a local SQLite query).
  Acking first keeps that safe.

### 5.6 `post(channel_id, text, thread_id=None)` and `display_name(user_id)`

- `post`: `chat.postMessage(channel=…, text=…, thread_ts=thread_id)`.
- `display_name`: `users.info`, then `profile.display_name` → `profile.real_name` → `name` →
  `user_id`. The result is cached in a dict for the lifetime of the process, and it never raises.

### 5.7 `slack-manifest.yaml`

```yaml
display_information:
  name: Games Leaderboard
  description: Tracks daily game results and posts leaderboards
features:
  bot_user:
    display_name: leaderboard
    always_online: true
  slash_commands:
    - command: /leaderboard
      description: Show game leaderboards
      usage_hint: "weekly maptap | maptap avg month | help"
      should_escape: false
oauth_config:
  scopes:
    bot: [groups:history, chat:write, users:read, app_mentions:read, commands]
settings:
  event_subscriptions:
    bot_events: [message.groups, app_mention]
  interactivity:
    is_enabled: true            # harmless; verify during setup whether slash commands need it
  org_deploy_enabled: false
  socket_mode_enabled: true
  token_rotation_enabled: false
```

---

## 6. Tasks

- [ ] `normalize_text`
- [ ] `_to_message` with subtype filtering
- [ ] Construction: retry handler, proxy, SSL context, `auth.test`
- [ ] `fetch_history` with thread replies and pagination
- [ ] `run` with the event, mention and slash-command handlers
- [ ] `post`, `display_name` with its cache
- [ ] `slack-manifest.yaml`

## 7. Acceptance criteria

`tests/test_slack_adapter.py` (no network; dispatch helpers are called directly with sample event
payloads, and the `WebClient` is a stub):
- [ ] Every row of the `normalize_text` table
- [ ] `_to_message` keeps the plain and kept subtypes, and drops bot, join and topic events
- [ ] `posted_at` is tz-aware UTC, and `thread_id` is set only for replies
- [ ] `message_changed` calls `on_message` with the **new** text. `message_deleted` calls
      `on_message_deleted` with `deleted_ts`.
- [ ] A mention strips the bot mention and replies in a thread
- [ ] The slash command acks before calling the handler, and responds in the channel
- [ ] `fetch_history` pages through a 2-page history stub and includes thread replies without duplicating parents
- [ ] `display_name` falls back correctly, caches, and returns `user_id` when the API errors
- [ ] A handler exception is logged, not raised

## 8. Out of scope

Block Kit formatting, multiple workspaces, OAuth install flows (it's an internal app), other platforms.

## 9. Open questions

- Is the private channel on a free Slack plan? If so, history is limited to 90 days, which limits
  the backfill.
