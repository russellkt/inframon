# Design: Migrate ak Maintenance to OpenFang Hands

**Date:** 2026-03-13
**Status:** Approved
**Project:** inframon + agent-knowledge

---

## Problem

The `ak` knowledge maintenance pipeline currently runs as two launchd processes on the Mac mini:
- `com.agent-knowledge.ingest` — `ak ingest --watch` persistent daemon
- `com.agent-knowledge.snapshot` — nightly `snapshot-all.sh` at 2am (embed-backfill → dedup → tidy → enrich → snapshot → link-detect)

This creates friction for multi-machine setups. The goal is zero scheduled processes on dev machines, with all LLM-heavy maintenance centralized on OpenFang VM101.

---

## Architecture

```
Mac mini (session-end hook only)
  └─ ak ingest (one-shot, already exists)
  └─ curl POST /webhook → OpenFang VM101 → ak-enrich Hand (immediate)

OpenFang VM101
  ├─ Hands
  │   ├─ ak-enrich    every 2h + webhook-triggered after session ingest
  │   ├─ ak-tidy      Workflow-only + on-demand via Matrix
  │   ├─ ak-snapshot  Workflow-only + on-demand via Matrix
  │   └─ ak-digest    triggered by ContentMatch after ak-maintenance Workflow
  │
  ├─ Workflow: ak-maintenance  (every 6h)
  │   step 1: embed-backfill (sequential)
  │   step 2: dedup per project (fan-out, parallel)
  │   step 3: tidy (sequential)
  │   step 4: enrich (sequential)
  │   step 5: snapshot (sequential)
  │   step 6: link-detect (sequential)
  │   step 7: "ak-maintenance complete" (triggers ak-digest via ContentMatch)
  │
  └─ Trigger: ContentMatch "ak-maintenance complete" → ak-digest Hand

Data layer
  └─ pg-ak at 100.127.176.3:5432 (Tailscale, reachable from VM101)
  └─ LLM: google/gemini-2.5-flash via OpenRouter BYOK (AK_LLM_MODEL)
```

---

## Components

### Hands

#### `ak-enrich`
- **Triggers:** Cron every 2h + webhook POST from Mac mini session-end hook
- **Task:** `ak enrich <project>` per project — fixes miscategorized memories, improves content
- **Model:** `google/gemini-2.5-flash` via OpenRouter
- **Output:** Silent unless errors. JSON report to logs.
- **System prompt:** Derived from `~/.pi/agent/agents/ak-enrich.md`

#### `ak-tidy`
- **Triggers:** Workflow-only + on-demand via Matrix message to inframon
- **Task:** `ak tidy <project> --apply` — dedup merge, forget low-quality, supersede outdated
- **Model:** `google/gemini-2.5-flash` via OpenRouter
- **Output:** Silent unless changes made or errors

#### `ak-snapshot`
- **Triggers:** Workflow-only + on-demand via Matrix
- **Task:** `ak snapshot <project>` per project — regenerates cached snapshots when memories changed
- **Model:** `google/gemini-2.5-flash` via OpenRouter
- **Output:** Silent (logs if LLM was called = something changed)

#### `ak-digest`
- **Triggers:** ContentMatch trigger on "ak-maintenance complete"
- **Task:** Cross-project synthesis, contradiction detection, pattern identification
- **Model:** `google/gemini-2.5-flash` via OpenRouter
- **Output:** Posts report to `#ak-digest` Matrix room (room to be created separately)
- **System prompt:** Derived from `~/.pi/agent/agents/ak-digest.md`

### Workflow: `ak-maintenance`

Runs every 6 hours. Steps:

| Step | Mode | Command |
|------|------|---------|
| 1 | sequential | `ak embed-backfill` |
| 2 | fan-out | `ak dedup <project> --merge` per project |
| 3 | collect | collect dedup results |
| 4 | sequential | `ak tidy --all --apply` |
| 5 | sequential | `ak enrich --all` |
| 6 | sequential | `ak snapshot --all` |
| 7 | sequential | `ak link-detect` |
| 8 | sequential | output "ak-maintenance complete" (triggers ak-digest) |

Error mode: `skip` per step (pipeline continues on individual failures).

### Trigger

```toml
[[trigger]]
name = "ak-digest-trigger"
pattern = { type = "ContentMatch", substring = "ak-maintenance complete" }
agent = "ak-digest"
max_fires = 0  # unlimited
```

### Mac mini Session-End Hook

Replaces the `--watch` daemon. After `ak ingest` completes:

```bash
curl -s -X POST http://10.10.1.127:8460/webhook \
  -H "X-Webhook-Secret: $WEBHOOK_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"event":"ak_ingest_complete","host":"'"$(hostname)"'"}'
```

---

## Docker Changes

### `Dockerfile.openfang`
Add Go install + `ak` binary build:
```dockerfile
RUN apt-get install -y golang-go \
 && go install github.com/russellkt/agent-knowledge/cmd/ak@latest
```

### `docker-compose.openfang.yml`
Add env vars:
```yaml
- AK_DB_URL=postgres://ak:...@100.127.176.3:5432/agent_knowledge
- AK_LLM_URL=https://openrouter.ai/api/v1
- AK_LLM_MODEL=google/gemini-2.5-flash
- AK_LLM_API_KEY=${OPENROUTER_API_KEY}
```

---

## Mac Mini Changes

1. Remove `com.agent-knowledge.ingest` launchd plist (`launchctl unload` + delete file)
2. Remove `com.agent-knowledge.snapshot` launchd plist (`launchctl unload` + delete file)
3. Update session-end hook to add webhook POST after `ak ingest`

---

## New Agent Files

```
openfang/agents/
  ak-enrich/agent.toml
  ak-tidy/agent.toml
  ak-snapshot/agent.toml
  ak-digest/agent.toml
```

---

## Out of Scope

- `#ak-digest` Matrix room creation (deferred)
- rsync/SSH catch-up mechanism from OpenFang to Mac mini (future)
- `ak-digest` posting output (deferred until room exists — Hand runs but output goes to logs)
- SSH-based `ak` execution (option C, deferred)
