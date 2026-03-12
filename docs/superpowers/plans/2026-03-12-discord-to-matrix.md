# Discord to Matrix Channel Migration

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Discord channel adapter with Matrix for lighter-weight infrastructure alert monitoring.

**Architecture:** OpenFang has a built-in Matrix adapter using Client-Server API long-polling (`/sync`). We create a Matrix bot account, configure OpenFang to use it, remove the Discord config, and update Docker environment accordingly.

**Tech Stack:** OpenFang Matrix adapter (built-in), Matrix Client-Server API

---

## Pre-Implementation Decision: Homeserver

Before starting, decide which Matrix homeserver to use:

| Option | Pros | Cons |
|--------|------|------|
| **matrix.org** (public) | Zero setup, instant start | Third-party dependency, rate limits |
| **Self-hosted Conduit** | Lightweight (single binary, ~10MB RAM), runs on Proxmox | Extra container/VM to maintain |
| **Self-hosted Synapse** | Most mature, full-featured | Heavy (Python, PostgreSQL, 500MB+ RAM) |

**Recommendation:** Start with **matrix.org** to validate the integration, then self-host later if desired. The config change is just `homeserver_url`.

---

## Chunk 1: Matrix Bot Setup & Configuration

### Task 1: Create Matrix Bot Account & Get Access Token

**Files:** None (external setup)

- [ ] **Step 1: Register bot account**

  Go to https://app.element.io and create a new account:
  - Username: `inframon-bot` (or similar)
  - Server: `matrix.org` (or your self-hosted homeserver)
  - Save the full user ID (e.g., `@inframon-bot:matrix.org`)

- [ ] **Step 2: Get access token via Element**

  In Element Web: Settings > Help & About > scroll to "Access Token" (click to reveal). Copy it.

  Alternatively, via curl:
  ```bash
  curl -s -X POST https://matrix.org/_matrix/client/v3/login \
    -H "Content-Type: application/json" \
    -d '{"type":"m.login.password","user":"inframon-bot","password":"YOUR_PASSWORD"}' \
    | python3 -m json.tool
  ```
  The `access_token` field in the response is what you need (`syt_...`).

- [ ] **Step 3: Create a room for infra alerts**

  In Element: Create Room > Name it "inframon" or "infra-alerts" > set to private.
  Note the room ID (Settings > Advanced > Internal room ID, format: `!abc123:matrix.org`).

- [ ] **Step 4: Invite the bot to the room**

  In the room, invite `@inframon-bot:matrix.org`. Accept the invite from the bot's session (or it auto-joins on first `/sync`).

### Task 2: Add Matrix Token to Environment

**Files:**
- Modify: `.env`

- [ ] **Step 1: Add MATRIX_TOKEN to .env**

  Add to `.env`:
  ```
  # ── Matrix ─────────────────────────────────────────────────────────
  MATRIX_TOKEN=syt_YOUR_ACCESS_TOKEN_HERE
  ```

- [ ] **Step 2: Verify .env is in .gitignore**

  ```bash
  grep -q "^\.env$" .gitignore && echo "OK" || echo "MISSING"
  ```
  Expected: OK

### Task 3: Update OpenFang Config

**Files:**
- Modify: `openfang/config.toml`

- [ ] **Step 1: Comment out Discord channel config**

  Replace the Discord block:
  ```toml
  # Discord disabled — migrated to Matrix (2026-03-12)
  # [channels.discord]
  # bot_token_env = "DISCORD_BOT_TOKEN"
  # default_agent = "inframon"
  # allowed_users = ["1124442795919286332"]
  ```

- [ ] **Step 2: Add Matrix channel config**

  Add after the webhook block:
  ```toml
  [channels.matrix]
  homeserver_url = "https://matrix.org"
  access_token_env = "MATRIX_TOKEN"
  user_id = "@inframon-bot:matrix.org"
  default_agent = "inframon"

  [channels.matrix.overrides]
  output_format = "markdown"
  ```

  Note: Replace `@inframon-bot:matrix.org` with the actual bot user ID from Task 1.

- [ ] **Step 3: Commit config change**

  ```bash
  git add openfang/config.toml
  git commit -m "feat: switch channel from Discord to Matrix"
  ```

### Task 4: Update Docker Compose

**Files:**
- Modify: `docker-compose.openfang.yml`

- [ ] **Step 1: Replace Discord env var with Matrix**

  In the `environment` section, replace:
  ```yaml
      - DISCORD_BOT_TOKEN=${DISCORD_BOT_TOKEN}
  ```
  with:
  ```yaml
      - MATRIX_TOKEN=${MATRIX_TOKEN}
  ```

- [ ] **Step 2: Commit docker-compose change**

  ```bash
  git add docker-compose.openfang.yml
  git commit -m "feat: pass MATRIX_TOKEN instead of DISCORD_BOT_TOKEN in docker env"
  ```

---

## Chunk 2: Validation & Cleanup

### Task 5: Deploy and Test

**Files:** None (runtime validation)

- [ ] **Step 1: Rebuild and start**

  ```bash
  docker compose -f docker-compose.openfang.yml up -d --build
  ```

- [ ] **Step 2: Check logs for Matrix connection**

  ```bash
  docker compose -f docker-compose.openfang.yml logs -f 2>&1 | head -50
  ```
  Expected: Log line like `channel connected channel=matrix` or `Matrix adapter started`.
  If error: check token validity, homeserver URL, bot user ID.

- [ ] **Step 3: Send test message in Matrix room**

  In Element (or any Matrix client), send a message in the infra-alerts room:
  ```
  @inframon-bot:matrix.org status
  ```
  Or just send "hello" — the bot should respond via the inframon agent.

- [ ] **Step 4: Test webhook still works**

  Verify the webhook channel (port 8460) is unaffected:
  ```bash
  curl -s http://localhost:8460/health
  ```

### Task 6: Update Documentation

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update CLAUDE.md interface line**

  Change:
  ```
  - **Interface:** Discord bot (@bmic-inframon) + webhook gateway (port 8460)
  ```
  to:
  ```
  - **Interface:** Matrix bot (@inframon-bot:matrix.org) + webhook gateway (port 8460)
  ```

- [ ] **Step 2: Update Environment Variables section**

  Replace `DISCORD_BOT_TOKEN` with `MATRIX_TOKEN` in the env vars list.

- [ ] **Step 3: Commit docs update**

  ```bash
  git add CLAUDE.md
  git commit -m "docs: update CLAUDE.md for Matrix channel"
  ```

### Task 7: Update Beads Memory

- [ ] **Step 1: Record the channel migration**

  ```bash
  bd remember "matrix-replaced-discord-for-inframon: Matrix replaced Discord as channel adapter (2026-03-12). Bot @inframon-bot:matrix.org on matrix.org homeserver. MATRIX_TOKEN env var. Discord was dropped due to heavy client. Webhook channel on port 8460 unchanged."
  ```

- [ ] **Step 2: Push changes**

  ```bash
  git push
  ```

---

## Summary of Changes

| File | Change |
|------|--------|
| `.env` | Add `MATRIX_TOKEN`, keep `DISCORD_BOT_TOKEN` (unused, for rollback) |
| `openfang/config.toml` | Comment out `[channels.discord]`, add `[channels.matrix]` |
| `docker-compose.openfang.yml` | Replace `DISCORD_BOT_TOKEN` with `MATRIX_TOKEN` in environment |
| `CLAUDE.md` | Update interface description and env var list |

## Rollback

If Matrix doesn't work out, uncomment the Discord block in `config.toml`, restore the env var in `docker-compose.openfang.yml`, and redeploy. The Discord bot token is still in `.env`.
