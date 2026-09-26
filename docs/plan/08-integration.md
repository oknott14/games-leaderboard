# Workstream H — Integration & End-to-End Verification

## 1. Goal

Prove the assembled system works: first with an automated end-to-end test using the real
components and a fake port, then with a manual run against the real Slack workspace.

## 2. Owns

- `tests/test_e2e.py`
- The verification record: the checklist in §6 below, ticked in a PR with notes

## 3. Depends on

F (runtime) and G (the Slack app and tokens) merged. That implies A–E too.

## 4. Provides

Confidence to switch the bot on for the group.

---

## 5. Automated end-to-end test (`tests/test_e2e.py`)

It uses the **real** games from `games/`, the real `boards.yaml`, built-ins and the example plugin,
a temporary SQLite file, and `FakePort`. There's no network.

1. Seed `FakePort.history` with about 3 weeks of messages for 3 players across MapTap, Krillion and
   TimeGuessr, from `SAMPLES`. Include:
   - a double post on one day
   - a message at 23:30 local time
   - a non-game message
   - a thread reply
2. `service.reparse()`, then `service.backfill(port)`. Check the expected result count.
3. Run `service.on_command(...)` for each of `weekly lastweek`, `daily yesterday maptap`,
   `average`, `top_score`, `recent_form`, `wins`, `most_improved`, `top_round`,
   `maptap avg month`, `tg median last_n=3`, `top3_avg`, `help`, `boards`, `wekly`. Each output
   must contain the expected leader or the expected text (not full snapshots, which are brittle).
4. Edit a message through `on_message` with a new score, and check the leader changes. Delete it,
   and check the player drops out.
5. `run_schedule_entry` for the weekly schedule entry posts one message containing all three boards.
6. Run it again: a second `backfill` changes no counts (idempotent).

## 6. Manual verification against Slack

Record the date, who ran it, and notes for each step in the PR.

- [ ] `uv run pytest` passes on `main`
- [ ] `leaderboard parse`, fed real pasted shares for every enabled game, shows the right scores, rounds and values
- [ ] `leaderboard check` lists the games, boards, registries (including the example plugin) and the schedule
- [ ] `docker compose up -d --build`. The logs show `Slack auth OK`, the plugins loaded, the reparse
      count, the backfill count and the Socket Mode connection.
- [ ] The backfilled history matches what people remember (spot-check last week's leader)
- [ ] Post a game result, then `@leaderboard today` gives a threaded reply that includes it
- [ ] `/leaderboard weekly` gives an in-channel response
- [ ] `@leaderboard maptap avg month` and `@leaderboard top_round` give correct ad-hoc and value boards
- [ ] Edit the posted result, and the board updates. Delete it, and it disappears.
- [ ] Add a board to `boards.yaml` using `top3_avg`, run `docker compose restart bot`, and query it
- [ ] Temporarily set a schedule cron for 2 minutes from now, restart, and the auto-post appears. Revert it afterwards.
- [ ] Stop the bot, post a result, start the bot, and the backfill picks it up
- [ ] Sleep the laptop for more than 10 minutes, wake it, and the socket reconnects on its own (check the logs)

## 7. Acceptance criteria

- [ ] `tests/test_e2e.py` passes
- [ ] Every item in §6 is ticked, with notes
- [ ] Any bugs found are filed against the owning workstream and fixed, or listed as known issues in the root README

## 8. Out of scope

Load testing (unnecessary at this scale) and multi-channel setups beyond one channel.
