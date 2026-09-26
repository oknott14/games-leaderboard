# T-703 · Work-laptop organisational checklist

| | |
|---|---|
| **Workstream** | G — Ops, Docker & Slack app setup ([plan](../plan/07-ops-setup.md)) |
| **Depends on** | — (can start immediately) |
| **Blocks** | [T-802](T-802-manual-slack-verification.md) |
| **Size** | S (≤ 1 day) |
| **Needs** | Input or action from the project owner |

## Files

- `docs/plan/07-ops-setup.md` (tick the checklist, record the answers)
- `docs/plan/decisions.md` (record the outcomes)

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [07-ops-setup.md](../plan/07-ops-setup.md) §5.5

## Scope

- With the project owner, confirm: Slack app approval, Docker Desktop licensing (or pick Colima, Rancher, Podman or native `uv`), the software/MDM policy, the data policy, and the proxy/TLS-inspection situation.

## Acceptance criteria

- [ ] Every organisational item is resolved, with decisions recorded.
- [ ] If a proxy or CA is needed, the values are documented for T-704.
- [ ] PR reviewed and merged
