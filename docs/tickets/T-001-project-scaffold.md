# T-001 · Project scaffold

| | |
|---|---|
| **Workstream** | 0 — Contracts & scaffold ([plan](../plan/00-contracts.md)) |
| **Depends on** | — (can start immediately) |
| **Blocks** | [T-002](T-002-ports-and-models.md), [T-003](T-003-game-config-schema.md), [T-004](T-004-boards-contracts.md), [T-701](T-701-docker.md) |
| **Size** | S (≤ 1 day) |

## Files

- `pyproject.toml`
- `uv.lock`
- `.gitignore`
- `src/leaderboard/__init__.py`
- `src/leaderboard/boards/__init__.py` (empty for now)
- `src/leaderboard/adapters/__init__.py`
- `src/leaderboard/cli.py` (placeholder `main()` returning 0)
- `tests/test_smoke.py`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [00-contracts.md](../plan/00-contracts.md) §7

## Scope

- Create the `uv` project for Python 3.12 using a `src/` layout and the hatchling build backend.
- Dependencies: `slack-bolt`, `sqlalchemy>=2`, `pydantic>=2`, `pyyaml`, `apscheduler>=3.10,<4`, `tzdata`. Dev group: `pytest`.
- Console script `leaderboard = "leaderboard.cli:main"`, with a placeholder `main()` so the script resolves.
- `.gitignore`: `.venv/`, `__pycache__/`, `.env`, `data/`, `*.db`, `.pytest_cache/`.
- Commit `uv.lock`.

## Out of scope

- Any real module content (T-002 → T-005).

## Acceptance criteria

- [x] `uv sync` succeeds on a clean checkout.
- [x] `uv run pytest` runs and passes (one smoke test that imports `leaderboard`).
- [x] `uv run leaderboard` exits 0.
- [x] `uv run pytest` passes; committed and pushed to `master`
