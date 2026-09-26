# Workstream G — Ops, Docker & Slack App Setup

## 1. Goal

Make the bot easy to run on a (work) laptop. That means a container setup that needs no rebuild
for config changes, a native no-Docker path, the Slack app created in the workspace, and a
user-facing README covering setup and troubleshooting on corporate networks.

## 2. Owns

- `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `.env.example`
- `README.md` (repo root, user-facing). The plan docs live in `docs/plan/`, which this workstream doesn't own.
- The **Slack app in the workspace**: created from `slack-manifest.yaml` (the file is E's), with the
  tokens handed to the operator
- The **work-laptop checklist** (§5.5), completed with the project owner

## 3. Depends on

Only WS0 (`pyproject.toml`, the `leaderboard` script). It can be done in parallel with everything else;
the README's command examples come from [06-runtime.md](06-runtime.md).

## 4. Provides

A runnable deployment, and the Slack tokens and channel ID that H needs.

---

## 5. Design

### 5.1 `Dockerfile`

```dockerfile
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.7 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project      # cached dependency layer
COPY src ./src
RUN uv sync --frozen --no-dev
ENV PATH="/app/.venv/bin:$PATH"
CMD ["leaderboard", "run"]
```

`games/`, `boards.yaml` and `plugins/` are **not** baked into the image. They're mounted, so
editing them needs a restart, not a rebuild.

### 5.2 `docker-compose.yml`

```yaml
services:
  bot:
    build: .
    env_file: .env
    volumes:
      - ./data:/app/data                 # SQLite lives on the laptop
      - ./games:/app/games:ro
      - ./boards.yaml:/app/boards.yaml:ro
      - ./plugins:/app/plugins:ro
      # - ./corp-ca.pem:/app/corp-ca.pem:ro   # only if SSL_CERT_FILE is needed
    restart: unless-stopped
```

Day-to-day commands (for the README):

```bash
docker compose up -d --build                       # start
docker compose logs -f bot                         # watch
docker compose run --rm bot leaderboard check      # validate configs after editing
docker compose restart bot                         # apply config/plugin changes
docker compose run --rm bot leaderboard show weekly
pbpaste | docker compose run --rm -T bot leaderboard parse   # test a share text from the clipboard
```

**Native (no Docker):** `uv sync`, then `uv run --env-file .env leaderboard run`. Document this as
an equal alternative (see §5.5, point 2).

### 5.3 `.env.example`

Every variable from [06-runtime.md](06-runtime.md) §5.1, with a one-line comment each. Only the
three Slack values are uncommented.

### 5.4 Slack app setup (README section + one-time task)

1. Go to api.slack.com/apps, choose **Create New App → From a manifest**, pick the workspace, and
   paste `slack-manifest.yaml`.
2. **Basic Information → App-Level Tokens → Generate** with scope `connections:write`. This is `SLACK_APP_TOKEN` (`xapp-…`).
3. **Install to Workspace.** Workspace admin approval may be needed. Copy the **Bot User OAuth
   Token**; this is `SLACK_BOT_TOKEN` (`xoxb-…`).
4. In the private channel, run `/invite @leaderboard`.
5. Channel ID: open the channel details, and the ID is at the bottom (`C…`). This is `SLACK_CHANNEL_IDS`.
6. Keep the app **internal**. Never enable public distribution (see decision #2).

### 5.5 Work-laptop checklist

The bot only makes **outbound HTTPS/WSS connections on port 443** to `slack.com` and
`wss-primary.slack.com`, the same endpoints as the Slack desktop app. No inbound ports, firewall
changes or public URL are needed.

**Organisational (confirm before relying on it):**
- [ ] **Slack app approval.** Does the workspace require admin approval for new apps? The scopes are small: one private channel's history, posting, and reading names.
- [ ] **Docker Desktop licensing.** It's free only for organisations under 250 employees **and**
      under $10M revenue. Otherwise use a paid seat, or **Colima**, **Rancher Desktop** or
      **Podman Desktop** (all work with these files), or the native `uv` path.
- [ ] **Software / MDM policy.** Is installing a container runtime or running a persistent background process allowed?
- [ ] **Data policy.** The bot stores copies of channel messages on the laptop. Check the company
      policy. `STORE_NON_GAME_MESSAGES=false` keeps only game posts.

**Technical (troubleshooting section in the README):**

| Symptom | Likely cause | Fix |
|---|---|---|
| `CERTIFICATE_VERIFY_FAILED` | A TLS-inspecting proxy (Zscaler, Netskope, …) | Export the corporate root CA from Keychain Access as `corp-ca.pem`, mount it, and set `SSL_CERT_FILE=/app/corp-ca.pem` |
| Timeouts connecting to Slack | An explicit proxy is required | Set `HTTPS_PROXY=http://proxy:port` |
| Socket connects then drops repeatedly | The proxy blocks websockets | Ask IT to allow `wss-primary.slack.com`, or run on a personal machine or a Raspberry Pi |
| `invalid_auth` / `not_authed` | Wrong or rotated token | Re-copy the tokens (§5.4) |
| `not_in_channel` / no messages | Bot not invited | `/invite @leaderboard` |
| Gaps after the laptop slept | Expected | The startup backfill fills them; scheduled posts in the gap are skipped |

### 5.6 README outline (repo root)

1. What it does (3 lines plus an example output)
2. Quick start: Slack app setup (§5.4), then `.env`, then `docker compose up -d --build`
3. Native run with `uv`
4. **Adding a game**: paste a share into `leaderboard parse`, write the YAML, run `check`, restart. Link to [01-parsing.md](01-parsing.md) §5.1 for the extraction rules, with the note about emoji as `:shortcode:`.
5. **Leaderboards**: using boards in chat, ad-hoc commands, adding a board to `boards.yaml`, writing a plugin (link to the example plugin)
6. Commands reference (`help` output)
7. Work-laptop notes and troubleshooting (§5.5)
8. Development: `uv sync`, `uv run pytest`, and a link to `docs/plan/README.md`

---

## 6. Tasks

- [ ] `Dockerfile`, `.dockerignore` (`.venv`, `data`, `.git`, `.env`, `__pycache__`)
- [ ] `docker-compose.yml`, `.env.example`
- [ ] README per §5.6
- [ ] Create the Slack app, install it, invite the bot, and hand over the tokens and channel ID (securely, never in the repo)
- [ ] Work through the §5.5 organisational checklist with the project owner

## 7. Acceptance criteria

- [ ] `docker compose build` succeeds on a clean checkout
- [ ] `docker compose run --rm bot leaderboard check` passes with the mounted configs
- [ ] Editing `boards.yaml` and restarting takes effect with no rebuild
- [ ] The native `uv run --env-file .env leaderboard check` works
- [ ] The Slack app exists, is installed, and is invited to the channel. The tokens work
      (`auth.test` OK in the `run` logs).
- [ ] Every §5.5 organisational item is resolved or has a decision recorded

## 8. Out of scope

Cloud hosting, CI/CD, image registries.

## 9. Open questions (for the project owner)

- Does your organisation need a paid Docker Desktop licence? If so, which runtime: Colima, Rancher, Podman, or native `uv`?
- Is there a TLS-inspecting proxy or an explicit proxy on the work network?
- What's the channel ID, and which timezone defines "a day" for the group?
