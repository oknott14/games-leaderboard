# T-604 · CLI: run & backfill (Slack, SSL/proxy, shutdown)

| | |
|---|---|
| **Workstream** | F — Runtime: settings, CLI & scheduler ([plan](../plan/06-runtime.md)) |
| **Depends on** | [T-602](T-602-cli-skeleton-check.md), [T-204](T-204-backfill.md), [T-503](T-503-slack-history.md), [T-504](T-504-slack-live-events.md), [T-605](T-605-scheduler.md) |
| **Blocks** | [T-704](T-704-user-readme.md), [T-802](T-802-manual-slack-verification.md) |
| **Size** | M (1–3 days) |

## Files

- `src/leaderboard/cli.py`
- `tests/test_cli.py`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [06-runtime.md](../plan/06-runtime.md) §5.3 (`run`, `backfill`)
- [07-ops-setup.md](../plan/07-ops-setup.md) §5.5 (troubleshooting table)

## Scope

- Build the SSL context from `SSL_CERT_FILE` if it's set, and pass the proxy through to `SlackPort`.
- `run`: `load_all`, then the port and service, then `reparse`, then `backfill` (log both counts), then `start_scheduler`, then `port.run` (blocking). `SIGTERM`/`SIGINT` stop the scheduler and exit 0.
- `backfill [--days N]`.

## Acceptance criteria

- [ ] Unit test with `SlackPort` monkeypatched to `FakePort`: the startup order and log lines, and `--days` sets `since`.
- [ ] Manual: `uv run --env-file .env leaderboard run` connects (once T-702 has provided tokens).
- [ ] `uv run pytest` passes; committed and pushed to `master`
