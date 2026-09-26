# T-505 · Slack app manifest

| | |
|---|---|
| **Workstream** | E — Slack adapter ([plan](../plan/05-slack-adapter.md)) |
| **Depends on** | — (can start immediately) |
| **Blocks** | [T-702](T-702-slack-app-setup.md) |
| **Size** | S (≤ 1 day) |

## Files

- `slack-manifest.yaml`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [05-slack-adapter.md](../plan/05-slack-adapter.md) §5.7

## Scope

- Write the manifest exactly as in §5.7: Socket Mode, the 5 bot scopes, the 2 events and the `/leaderboard` command.
- Check that it's accepted by **Create app → From manifest** in a test workspace, or by the manifest validator.

## Acceptance criteria

- [ ] Slack accepts the manifest without errors.
- [ ] Record whether slash commands need `interactivity` (open note in `05-slack-adapter.md`).
- [ ] Committed and pushed to `master`
