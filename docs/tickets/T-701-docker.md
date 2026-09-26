# T-701 · Dockerfile, compose & .env.example

| | |
|---|---|
| **Workstream** | G — Ops, Docker & Slack app setup ([plan](../plan/07-ops-setup.md)) |
| **Depends on** | [T-001](T-001-project-scaffold.md) |
| **Blocks** | [T-704](T-704-user-readme.md), [T-802](T-802-manual-slack-verification.md) |
| **Size** | S (≤ 1 day) |

## Files

- `Dockerfile`
- `.dockerignore`
- `docker-compose.yml`
- `.env.example`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [07-ops-setup.md](../plan/07-ops-setup.md) §5.1–§5.3

## Scope

- Write the files as specified. Configs, boards and plugins are mounted, not baked into the image.
- `.env.example` lists every variable from `06-runtime.md` §5.1 with a comment.

## Acceptance criteria

- [ ] `docker compose build` succeeds.
- [ ] `docker compose run --rm bot leaderboard --help` works.
- [ ] Once T-602 merges, `leaderboard check` runs in the container with the mounted configs.
- [ ] PR reviewed and merged
