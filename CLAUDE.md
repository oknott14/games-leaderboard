# CLAUDE.md

A Slack bot that reads a private channel of daily web-game results (MapTap, TimeGuessr, Krillion,
…), stores them in SQLite, and posts configurable leaderboards. It runs locally over Socket Mode.

## Before changing anything

1. Read `docs/plan/README.md` (architecture, glossary, workstreams, working rules).
2. Work is done by ticket: read your ticket in `docs/tickets/` (the overview there has the order
   and dependencies), its "Read first" links, and `docs/plan/00-contracts.md`.
3. Only edit the files your ticket lists. Signatures, dataclass fields and schema fields in
   `00-contracts.md` are shared contracts. Change them only in a dedicated PR that updates both
   the doc and the stubs.
4. Record lasting decisions in `docs/plan/decisions.md`.

## Commands

- `uv sync`: install dependencies
- `uv run pytest`: tests (never hit the network; use the fakes in `tests/conftest.py`)
- `uv run leaderboard check`: validate `games/`, `boards.yaml` and `plugins/`
- `uv run leaderboard parse`: test a game share text (reads stdin)

## Conventions

- Python 3.12, `from __future__ import annotations`, type hints everywhere.
- The core never imports `slack_*`. Only `src/leaderboard/adapters/slack.py` does.
- Datetimes are tz-aware UTC in memory and naive UTC in the DB. `played_on` is a local-timezone date.
- Leaderboards are computed at query time. Never store derived standings.
