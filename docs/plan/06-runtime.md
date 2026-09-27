# Workstream F — Runtime: Settings, CLI & Scheduler

## 1. Goal

Wire everything into a runnable program: read settings, load configs and plugins, run the startup
routine (reparse, then backfill), start scheduled posts, and hand control to the Slack adapter.
Also provide the CLI people use to run and debug the bot.

## 2. Owns

- `src/leaderboard/settings.py`, `src/leaderboard/scheduler.py`, `src/leaderboard/cli.py`, `src/leaderboard/__main__.py`
- `tests/test_settings.py`, `tests/test_scheduler.py`, `tests/test_cli.py`

## 3. Depends on

A, B, C, D and E merged (it calls all of them). Before they merge, work can start against the
stubs, with tests that monkeypatch the pieces. [Contracts](00-contracts.md) §5.13.

## 4. Provides

The `leaderboard` console script and the Docker entrypoint.

---

## 5. Design

### 5.1 `Settings.from_env`

| Variable | Default | Notes |
|---|---|---|
| `SLACK_BOT_TOKEN` | — | `xoxb-…`. Required for `run` and `backfill`. |
| `SLACK_APP_TOKEN` | — | `xapp-…`. Required for `run`. |
| `SLACK_CHANNEL_IDS` | — | Comma-separated. Required for `run` and `backfill`. |
| `TIMEZONE` | `UTC` | IANA name. Defines "a day" and the cron times. |
| `DATABASE_URL` | `sqlite:///data/leaderboard.db` | |
| `GAMES_DIR` | `games` | |
| `BOARDS_FILE` | `boards.yaml` | |
| `PLUGINS_DIR` | `plugins` | |
| `BACKFILL_DAYS` | `90` | First-run backfill depth. |
| `STORE_NON_GAME_MESSAGES` | `true` | |
| `HTTPS_PROXY` | — | Corporate proxy. |
| `SSL_CERT_FILE` | — | Corporate root CA bundle (for TLS-inspecting proxies). |
| `LOG_LEVEL` | `INFO` | |

- Required values are checked **per command**, not at load, so `parse`, `check` and `show` work
  without Slack tokens.
- A missing required value raises `SystemExit("Missing SLACK_BOT_TOKEN (see .env.example)")`.
- `.env` isn't loaded by the app. Docker Compose's `env_file` handles it, and natively you run
  `uv run --env-file .env leaderboard …`.

### 5.2 Loading configs: `load_all(settings)`

1. `load_builtins()`, then `load_plugins(settings.plugins_dir)`
2. `games = load_games(settings.games_dir)`
3. `boards = load_boards(settings.boards_file, games)`

Any error prints the message (which already names the file) and exits with code 2. It never starts
half-configured.

### 5.3 CLI commands

| Command | Needs Slack | Behaviour |
|---|---|---|
| `run` | yes | `load_all`, then build the SSL context (from `SSL_CERT_FILE` if set), then `SlackPort`, then `LeaderboardService` (with `name_for = names_from(port)`, which adapts `display_name(user_id)` to `name_for(platform, user_id)`). Then `reparse()` (logs the count), `backfill()` (logs the count), `start_scheduler(...)`, and `port.run(service)`, which blocks. `SIGTERM` or `SIGINT` shuts the scheduler down and exits 0. |
| `backfill [--days N]` | yes | As in `run` up to the backfill, with `since = now − N days` when `--days` is given. Then exits. |
| `reparse` | no | `load_all`, then the service with no port, then `reparse()`. Prints the count. |
| `show <words…>` | optional | Prints `service.on_command(" ".join(words))`. Uses Slack names when a token is set, otherwise user ids. |
| `parse [text]` | no | Delegates to A's `parse_main`. |
| `check` | no | `load_all`, then prints every game with its values, every board with its composition, the registered windows, aggregators and board types (plugins marked), and the schedule. Exits 0 when the config is valid. |

Global flags: `--log-level`. Logging format: `%(asctime)s %(levelname)s %(name)s: %(message)s`.

### 5.4 Scheduler

**`start_scheduler(schedule, service, port, channel_ids, tz)`:**
- Returns `None` if the schedule is empty.
- Otherwise it creates a `BackgroundScheduler(timezone=tz)`, and adds one job per entry with
  `CronTrigger.from_crontab(entry.cron, timezone=tz)`, `misfire_grace_time=3600` and
  `coalesce=True`. Runs missed while the laptop was asleep are skipped or merged, never posted in
  bulk.
- The job calls `run_schedule_entry(entry, service, port, channel_ids, today=now(tz).date())`.

**`run_schedule_entry`:**
1. `anchor = resolve_anchor(entry.anchor, today)`
2. For each board name, `format_board(service.run_query(Query(board, None, anchor)), name_for)`.
3. Join the blocks with a blank line and post the message once to each channel with `port.post`.
4. Skip boards with no results. If every board is empty, post nothing and log instead.
5. Exceptions are logged and never propagated, so the scheduler keeps running.

---

## 6. Tasks

- [ ] `Settings.from_env` with per-command validation
- [ ] `load_all` with fail-fast errors
- [ ] CLI: `run`, `backfill`, `reparse`, `show`, `parse`, `check`
- [ ] SSL context and proxy passed through to `SlackPort`
- [ ] `start_scheduler` and `run_schedule_entry`
- [ ] Signal handling for a clean shutdown

## 7. Acceptance criteria

- [ ] `test_settings`: defaults, parsing booleans and lists, a missing required value names the variable
- [ ] `test_cli`:
  - `check` passes on the repo's real `games/` and `boards.yaml`
  - `check` exits 2 with the file name on a broken YAML
  - `show weekly` works against a temporary DB with a monkeypatched service
  - `parse` delegates to A
- [ ] `test_scheduler`:
  - `run_schedule_entry` with `FakePort` posts one combined message per channel, anchored at
    `last_week`'s Sunday
  - Nothing is posted when all boards are empty
  - An exception is logged, not raised
  - `start_scheduler([])` returns `None`
- [ ] Manual: `uv run --env-file .env leaderboard run` connects and logs the reparse and backfill counts

## 8. Out of scope

Hot-reloading configs without a restart (follow-up), and a daemon or launchd setup (Docker restart
policies cover this).

## 9. Open questions

- None yet.
