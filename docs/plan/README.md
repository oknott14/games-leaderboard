# Games Leaderboard — Build Plan

Start here. This folder is the plan for building the games leaderboard bot. The work is split into
**workstreams** that different people can build at the same time.

## What we're building

A private Slack channel has people posting daily web-game share results (MapTap, Krillion,
TimeGuessr, …). The bot:

- reads every message in that channel (backfill on startup + live events),
- recognises game results using **one YAML file per game** (regex-based, handles horizontal and
  vertical layouts and per-round scores),
- stores messages and parsed results in **SQLite via SQLAlchemy**,
- answers **any kind of leaderboard** (daily, weekly total, best average, top score, recent form,
  most daily wins, best round, …). Boards are **compositions of pluggable parts**: they're defined
  in YAML, can be requested ad hoc in chat, and can be extended with small Python plugins,
- responds to `@leaderboard …` mentions and the `/leaderboard …` slash command, and posts on a
  schedule,
- runs in **Docker on a laptop** (Slack Socket Mode, so no public URL and no cloud hosting),
- keeps Slack behind a platform-neutral **port**, so other chat platforms can be added later.

The reasons behind these choices are in [decisions.md](decisions.md).

## Architecture

```
              ┌─────────────────────────── core (platform-neutral) ────────────────────────────┐
Slack ⇄       │                                                                                 │
Socket Mode   │  SlackPort ─ChatMessage─▶ LeaderboardService ─▶ parser ◀─ games/*.yaml          │
(outbound     │  (adapter) ◀──text────── │     │                  │                             │
 443 only)    │                          │     ▼                  ▼                             │
              │                          │  SQLAlchemy ─▶ SQLite (messages, results, rounds)    │
              │                          ▼                                                      │
              │   commands ─▶ boards engine ◀─ boards.yaml + plugins/*.py                       │
              │               (values × windows × aggregators × board types → standings)        │
              │   scheduler (cron from boards.yaml) ─▶ boards engine ─▶ port.post              │
              └─────────────────────────────────────────────────────────────────────────────────┘
```

**Data flow for one message:** Slack event → `SlackPort` normalises it to a `ChatMessage` →
`LeaderboardService.on_message` stores it → `parse_message` extracts zero or more game results →
results and rounds are stored with the local-timezone `played_on` date.

**Data flow for one leaderboard request:** `@leaderboard weekly maptap` → `parse_command` → `Query`
→ `service.run_query` → `boards.engine.run_board` (for each game, using rows loaded by the service)
→ `BoardResult` → `format_board` → text posted back through the port.

## Glossary

| Term | Meaning |
|---|---|
| **Game config** | `games/<name>.yaml`. Says how to recognise a game's share text and which numbers it yields. |
| **Result** | One parsed game post: a player, a game, a date, a `score` and optional `rounds`. |
| **Value** | A number taken from a result. `score` always exists; games can declare more (e.g. `best_round` = max of rounds). |
| **Window** | Which results are in scope relative to an **anchor date** (`day`, `week`, `month`, `all`, `last_n: 5`, …). |
| **Aggregator** | How one player's values in the window become one number (`sum`, `avg`, `max`, `latest`, `streak`, …). |
| **Board type** | The whole computation. `ranked` = aggregate per player then rank. Others (e.g. `daily_wins`) compare players or periods. |
| **Board** | A named composition: type + value + window + aggregator + options. Defined in `boards.yaml` or built ad hoc from a chat command. |
| **Anchor** | The reference date a board is computed for (`today`, `yesterday`, `lastweek`, a date). |
| **Duplicate policy** | Per game: which post counts when a player posts the same game twice in one day (`first`, `best`, `last`). |
| **Port / adapter** | `ChatPort` is the platform-neutral interface; `SlackPort` is the Slack adapter implementing it. |
| **Contract** | A shared type or signature in [00-contracts.md](00-contracts.md) that several workstreams depend on. |

## Workstreams

```
                 ┌──────────────────────── 0. Contracts & scaffold (serial) ────────────────────────┐
                 ▼             ▼               ▼                ▼                ▼               ▼
            A. Parsing    B. Persistence   C. Boards       D. Commands &    E. Slack        G. Ops, Docker
            & game YAML   & service        engine          formatting       adapter         & Slack app
                 └─────────────┴───────────────┴────────────────┴────────────────┘
                                                   ▼
                                  F. Runtime: settings, CLI, scheduler
                                                   ▼
                                  H. Integration & end-to-end verification
```

| # | Workstream | Doc | Depends on | Size |
|---|---|---|---|---|
| 0 | Contracts & scaffold | [00-contracts.md](00-contracts.md) | — | S |
| A | Parsing & game configs | [01-parsing.md](01-parsing.md) | 0 | M |
| B | Persistence & service | [02-persistence-service.md](02-persistence-service.md) | 0 | M |
| C | Boards engine (C1 / C2 / C3) | [03-boards-engine.md](03-boards-engine.md) | 0 | L |
| D | Commands & formatting | [04-commands-formatting.md](04-commands-formatting.md) | 0 | M |
| E | Slack adapter | [05-slack-adapter.md](05-slack-adapter.md) | 0 | M |
| F | Runtime (settings, CLI, scheduler) | [06-runtime.md](06-runtime.md) | A–E | S |
| G | Ops, Docker & Slack app setup | [07-ops-setup.md](07-ops-setup.md) | 0 | S |
| H | Integration & verification | [08-integration.md](08-integration.md) | F, G | S |

Workstream 0 is the only step that must be done alone. Once its PR is merged, A, B, C, D, E and G
can all start at the same time. C is the largest, and it can be split between up to three people
(see its doc).

## Status

Work is tracked per **ticket**, not per workstream. Each workstream is broken into small tickets
in [`docs/tickets/`](../tickets/README.md). That overview holds the dependency graph, the order
tickets can run in, suggested lanes per engineer, and the **tracker** (owner and status for every
ticket). Branches and PRs are per ticket (`t-<nnn>-<slug>`).

## Working rules

1. **Stay in your files.** Each workstream doc lists the files it **owns**. Only edit those. If you
   need something from another workstream, depend on its contract and use a fake in tests.
2. **Contracts are shared.** Signatures, dataclass fields and Pydantic schema fields in
   [00-contracts.md](00-contracts.md) are shared. Workstream 0 creates them as stubs whose function
   bodies raise `NotImplementedError`. The workstream named next to each stub fills in the **body**
   without changing the signature.
3. **Changing a contract** takes its own small PR that updates both `00-contracts.md` and the stub
   code, and it's reviewed by the owners of every workstream that uses it. Don't bundle a contract
   change into a feature PR.
4. **Tests never touch the network.** Use the fakes in `tests/conftest.py` (`FakePort`,
   `sample_games`, `SAMPLES`, `make_rows`, `sessions`). Each workstream must be mergeable on its own.
5. **One branch and one PR per ticket** (`t-<nnn>-<slug>`, PR title `T-<nnn>: <title>`).
   `uv run pytest` must pass on every PR.
6. **Done means** every acceptance-criteria box in the ticket is ticked. A workstream is done when
   all its tickets are, and the acceptance criteria in its plan doc are met.
7. **Open questions** go in the "Open questions" section of the relevant doc. Resolve them in a PR
   and record lasting decisions in [decisions.md](decisions.md).

## Conventions

- Python 3.12, managed with `uv` (`uv sync`, `uv run pytest`, `uv run leaderboard …`).
- Package: `src/leaderboard/`. Tests: `tests/`, one `test_<module>.py` per module.
- Type hints everywhere, and `from __future__ import annotations` in every module.
- Datetimes: tz-aware UTC in memory at the port boundary, naive UTC in the database (SQLite).
  `played_on` dates are in the configured local timezone.
- Chat text uses a minimal shared markup: `*bold*`, `_italic_`, emoji. No Slack Block Kit in the core.
- Logging: `logging.getLogger(__name__)`. No `print` except in the CLI.

## Open items (need input from the project owner)

- Real samples of MapTap and TimeGuessr (tracked in [01-parsing.md](01-parsing.md) §9). Krillion's share format and scoring are fully specified.
- Docker Desktop licence status and corporate proxy setup (tracked in [07-ops-setup.md](07-ops-setup.md)).
- The channel ID and timezone.
- The starter set of boards and the auto-post schedule (tracked in [03-boards-engine.md](03-boards-engine.md)).

## Follow-ups (not in v1)

Per-person stat cards (`me`, `stats @user`), charts rendered as images, Alembic migrations,
hot-reload of boards without a restart, a privacy notice for the channel, and a second chat adapter.
