# Decision Log

Each entry records what was decided and why. Add new entries at the bottom. If a decision is
reversed, mark the old entry *Superseded by #N* instead of deleting it.

---

### 1. Python stack
**Decision:** Python 3.12 with Slack Bolt for Python, SQLAlchemy 2.0, Pydantic 2, PyYAML and
APScheduler 3, managed with `uv`.
**Why:** The core work is regex parsing and small-scale data aggregation, which Python keeps short.
Bolt for Python has first-class Socket Mode support. Pydantic gives strict YAML config validation
with readable errors.

### 2. Internal Slack app, not a distributed one
**Decision:** Build the app as an internal (single-workspace) app. Never publish it to the Slack Marketplace.
**Why:** Since 2025, Slack heavily rate-limits `conversations.history` and `conversations.replies`
for non-Marketplace apps that are *distributed* (about 1 request per minute, 15 messages per page).
Internal apps keep the normal Tier 3 limits, which makes a history backfill practical.

### 3. Private channel, with the bot invited
**Decision:** The game results channel is a private channel, and the bot is invited with `/invite`.
**Why:** Bots can be members of private channels (scope `groups:history`). They generally can't join
group DMs, which would need a user token acting as a person.

### 4. Socket Mode, running on a laptop
**Decision:** Use Slack Socket Mode and run the bot locally, in Docker or natively with `uv`.
**Why:** Socket Mode uses an outbound websocket on port 443, so it needs no public URL, tunnel or
cloud hosting. When the laptop is asleep the bot is offline. On startup it backfills missed messages
from channel history, so no results are lost (scheduled posts during downtime are skipped).

### 5. Store every message, parse at ingest, compute boards at query time
**Decision:** Store raw normalised messages, plus parsed results and rounds. Apply duplicate
policies and all leaderboard maths when a board is requested, and store none of it.
**Why:** Changing a game config, duplicate policy, value or board then applies to all of history
immediately. `reparse` rebuilds the results from the raw messages. At this scale (thousands of rows)
computing on demand is instant.

### 6. SQLite behind SQLAlchemy
**Decision:** SQLite in WAL mode, accessed only through SQLAlchemy ORM models. Tables are created
with `create_all`, and there are no migrations in v1.
**Why:** It's a single file with no server, which suits a laptop. The ORM keeps a move to Postgres
down to a `DATABASE_URL` change. Migrations aren't needed yet because the results can always be
re-derived from the stored messages.

### 7. One YAML file per game; regex extraction in three steps
**Decision:** Each game has `detect`, `score` and optional `rounds` (a block regex plus an item
regex), plus derived `values`. A Python `parser` plugin is the escape hatch for irregular formats.
**Why:** Layout (horizontal vs vertical) then needs no special handling. Scoping round extraction
to a block stops dates, puzzle numbers and totals from being counted as rounds.

### 8. Per-game duplicate policy
**Decision:** Each game's YAML sets `duplicates: first | best | last`, which decides which of a
player's posts counts when they post the same game more than once in a day.
**Why:** Different groups want different rules. `first` discourages re-rolling; `best` is lenient.

### 9. Leaderboards as compositions of pluggable parts
**Decision:** A board is value × window × aggregator × board type. Built-ins and plugins register
through the same decorators (`@window`, `@aggregator`, `@board_type`). Boards are defined in
`boards.yaml` or ad hoc from chat.
**Why:** It supports "any type of leaderboard" without a code change for most requests. New kinds
need only a small plugin file, and the built-ins double as plugin examples.

### 10. Both @mention and a slash command, sharing one parser
**Decision:** `@leaderboard …` replies in a thread; `/leaderboard …` responds in the channel. Both
call the same `on_command`.
**Why:** Mentions need no extra Slack setup. The slash command gives a cleaner experience. One
parser keeps their behaviour identical.

### 11. Scheduled posts defined in `boards.yaml`
**Decision:** Auto-posts are `schedule:` entries (cron + boards + anchor) in `boards.yaml`, and
aren't set through environment variables.
**Why:** Any board can be scheduled, and the schedule sits next to the board definitions.

### 12. Platform-neutral core behind `ChatPort`
**Decision:** The core imports only `ports.py`, never `slack_*`. Slack lives in `adapters/slack.py`.
**Why:** It keeps the option of other platforms open, and it lets every core component be tested
with a `FakePort`.

### 13. Privacy handling deferred
**Decision:** v1 has no privacy notice or data-retention controls, except the
`STORE_NON_GAME_MESSAGES=false` option.
**Why:** The project owner chose to deal with privacy later. It's tracked as a follow-up, and the
work-laptop IT checklist in `07-ops-setup.md` flags it.
