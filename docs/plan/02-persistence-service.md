# Workstream B — Persistence & Service

## 1. Goal

Store messages and parsed results in SQLite, keep them correct through edits, deletes, backfills
and config changes, and connect the pieces: chat events and commands come in, parsed results and
board output go out. `LeaderboardService` is the one object the chat adapter talks to.

## 2. Owns

- `src/leaderboard/db.py`
- `src/leaderboard/service.py`
- `tests/test_db.py`, `tests/test_service.py`

**Must not edit:** `models.py` (WS0's contract), the parser (A), the engine (C), or commands and
formatting (D). The service **calls** those.

## 3. Depends on

[Contracts](00-contracts.md) §5.1 ports, §5.3 `parse_message`, §5.4 models, §5.8 `run_board` and
`board_applies`, §5.9 `parse_command`, §5.10 formatting, §5.11 this workstream's signatures, and §6
fakes (`sessions`, `FakePort`, `sample_games`).

Until A, C and D merge, test with **monkeypatched stand-ins**: a trivial `parse_message` that
matches `"TEST <n>"`, a `run_board` that returns the rows as standings, and a `parse_command` that
returns a fixed `Query`.

## 4. Provides

- `make_session_factory(url)`, used by F.
- `LeaderboardService`, the `ChatHandler` used by E and F, and `run_query` used by the scheduler (F).

---

## 5. Design

### 5.1 `db.py`

`make_session_factory(url)`:
- For SQLite file URLs, creates the parent directory (`make_url(url).database`).
- `create_engine(url)`. For SQLite, a `connect` event listener runs `PRAGMA foreign_keys=ON` and
  `PRAGMA journal_mode=WAL` (so the CLI can read while the bot writes) and `busy_timeout=5000`.
- `Base.metadata.create_all(engine)`.
- Returns `sessionmaker(engine, expire_on_commit=False)`.

### 5.2 Time handling

- `ChatMessage.posted_at` is tz-aware UTC and is stored as **naive UTC** (`dt.astimezone(UTC).replace(tzinfo=None)`).
- `played_on = posted_at (UTC) → astimezone(tz) → .date()`. The day boundary is **local midnight**
  in the configured timezone.
- `today()` defaults to `datetime.now(tz).date()`. It's injectable for tests.

### 5.3 Ingest: `on_message(msg)`

1. If `msg.channel_id` isn't in `channel_ids`, ignore it.
2. Parse first: `results = parse_message(msg.text, games.values())`.
3. In one transaction:
   - Look up the message by `(platform, channel_id, message_id)`.
   - **New:** if `results` is empty and `store_non_game` is false, stop. Otherwise insert the message.
   - **Existing (an edit or a backfill replay):** update `text`, `user_id` and `thread_id`. Set
     `edited_at = now` only if the text changed. Clear `message.results` (delete-orphan cascades
     to the rounds).
   - Insert one `GameResult` per `ParsedResult`, with `GameRound` rows numbered from 1.
4. This is **idempotent**: replaying the same message gives the same state. Backfill relies on that.

Duplicates, meaning the same player posting the same game twice in one day, are **not** resolved
here. Every result is stored, and the engine applies the game's policy at query time (decision #5).

### 5.4 `on_message_deleted`

Deletes the matching `Message`, if any. The cascade removes its results and rounds.

### 5.5 `reparse() -> int`

In one transaction, deletes every `GameResult` (bulk delete, then rounds via FK cascade), then
re-parses every stored `Message` in `posted_at` order and inserts the results. Returns the number
of results. Runs on every startup (F), so edits to game YAML apply after a restart.

### 5.6 `backfill(port, *, since=None, default_days=90) -> int`

For each channel in `channel_ids`:
- Start from `since` if given. Otherwise use `latest_posted_at(channel) − 1 day` (to catch recent
  edits), or `now − default_days` if nothing is stored yet.
- `for msg in port.fetch_history(channel, oldest): self.on_message(msg)`
- Log each channel's count, and return the total count of messages processed.

### 5.7 `run_query(query) -> BoardResult`

1. Games in scope are `query.games` (in games-dict order) or all games. Keep those where
   `board_applies(query.board, game)` is true.
2. For each game, build a `load_rows(range)` closure. It selects `GameResult` rows for the game
   with `played_on` in the range (`start=None` means no lower bound), eager-loads the rounds, and
   maps them to `ResultRow` (`player = (platform, user_id)`, rounds ordered by `round_no`).
3. `standings = run_board(query.board, game, query.anchor, load_rows)`.
4. The result is `BoardResult(board, anchor, board_range(board, anchor), board_unit(board), sections)`.
   It keeps only sections with standings.

### 5.8 `on_command(text) -> str`

```
parsed = parse_command(text, today=self.today(), games=self.games, boards=self.boards.boards)
Query        → format_board(self.run_query(parsed), self.name_for)
InfoRequest  → format_info(parsed.topic, self.games, self.boards.boards)
CommandError → format_error(parsed)
```
Any unexpected exception is logged with its traceback, and the reply is
`"Sorry, something went wrong — check the bot logs."`. The bot must never go silent.

### 5.9 `latest_posted_at(platform, channel_id)`

Returns `max(Message.posted_at)` for that channel as tz-aware UTC, or `None`.

---

## 6. Tasks

- [ ] `db.py` with the pragmas and directory creation
- [ ] Time helpers (`to_db`, `from_db`, `local_date`)
- [ ] `on_message` upsert and parse, `on_message_deleted`
- [ ] `reparse`, `backfill`, `latest_posted_at`
- [ ] `run_query` with the `load_rows` closure
- [ ] `on_command` dispatch and the error fallback

## 7. Acceptance criteria

`tests/test_db.py`:
- [ ] Creates a missing directory. Foreign keys are enforced (deleting a message cascades to its
      results and rounds). WAL mode is on.

`tests/test_service.py` (the `sessions` fixture, `FakePort`, and stand-ins until A, C and D merge):
- [ ] A new game message stores one message plus its results and rounds, with `played_on` in the local timezone
- [ ] A message at 23:30 local time and one at 00:30 the next day get different `played_on` dates,
      even when both fall on the same UTC date
- [ ] An edit that changes the score replaces the results, and `edited_at` is set
- [ ] An edit that removes the game text removes the results
- [ ] A delete removes the message, results and rounds
- [ ] A message from another channel is ignored
- [ ] `store_non_game=False`: non-game messages aren't stored, game messages are
- [ ] Replaying the same backfill twice leaves an identical row count
- [ ] Backfill `since` follows the rules (explicit `since`, latest minus 1 day, `default_days`)
- [ ] `reparse` after swapping in a game config with a different score regex produces new scores
- [ ] `run_query` passes only rows in the range to `run_board`, and skips games that don't apply
- [ ] `on_command` routes `Query`, `InfoRequest` and `CommandError`, and an exception becomes the
      fallback reply

## 8. Out of scope

Alembic migrations, multi-workspace support, per-person stats queries (follow-up).

## 9. Open questions

- None yet.
