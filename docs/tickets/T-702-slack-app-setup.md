# T-702 · Create the Slack app & collect tokens

| | |
|---|---|
| **Workstream** | G — Ops, Docker & Slack app setup ([plan](../plan/07-ops-setup.md)) |
| **Depends on** | [T-505](T-505-slack-manifest.md) |
| **Blocks** | [T-802](T-802-manual-slack-verification.md) |
| **Size** | S (≤ 1 day) |
| **Needs** | Input or action from the project owner |

## Files

- (no repo files) Slack workspace configuration

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [07-ops-setup.md](../plan/07-ops-setup.md) §5.4

## Scope

- Create the app from the manifest, generate the app-level token (`connections:write`), install it (getting admin approval if needed), `/invite @leaderboard` in the private channel, and note the channel ID.
- Hand the tokens and channel ID to the operator **securely**, never in the repo or chat history.
- Keep the app internal (decision #2).

## Acceptance criteria

- [ ] The app is installed and in the channel.
- [ ] `auth.test` succeeds with the bot token.
- [ ] The operator has `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN` and `SLACK_CHANNEL_IDS`.
- [ ] PR reviewed and merged
