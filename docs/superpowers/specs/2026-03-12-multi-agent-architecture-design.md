# Multi-Agent Architecture for Inframon

**Date:** 2026-03-12
**Status:** Approved

## Problem

Inframon runs as a single OpenFang agent (`inframon`) handling all responsibilities: interactive human Q&A, Zabbix webhook alert triage, and (theoretically) proactive monitoring. This creates several issues:

- **Bloated system prompt** (~190 lines) covering investigation protocols, suppression rules, notification routing, tool docs, and conversational behavior — dilutes LLM attention
- **Context pollution** — webhook alert processing shares session context with human chat
- **Purely reactive** — no proactive monitoring; issues only surface when Zabbix fires an alert
- **No separation of concerns** — one agent optimizing for three fundamentally different execution modes

## Architecture

### Agent Topology

Three agents, each optimized for its execution mode:

#### `inframon` — Interactive Agent
- **Type:** Regular agent (`builtin:chat`)
- **Trigger:** Human messages via Matrix
- **Purpose:** Answer questions, run ad-hoc investigations on request
- **System prompt:** ~40 lines. Conversational, concise. References skills but doesn't embed investigation protocols or suppression rules.
- **Matrix room:** `#inframon` — receives and responds via native Matrix channel
- **Skills:** All monitoring skills (proxmox, zabbix, juniper, pbs, truenas, infrastructure-reference, email-notify, matrix-notify)
- **Capabilities:** `tools = ["file_read", "file_write", "file_list", "shell_exec", "web_fetch", "memory_store", "memory_recall", "channel_send"]`, `memory_write = ["self.*", "shared.*"]`, `memory_read = ["*"]`. Retains `channel_send` for native Matrix channel responses.

#### `inframon-triage` — Alert Handler Agent
- **Type:** Regular agent (`builtin:chat`)
- **Trigger:** Zabbix webhook events on port 8460 (webhook channel `default_agent = "inframon-triage"`)
- **Purpose:** Receive alerts, follow investigation protocol, notify or suppress
- **System prompt:** ~60 lines. Strict, procedural. Contains the investigation protocol and suppression rules — nothing else.
- **Notifications:** Sends to `#inframon-alerts` Matrix room via `matrix-notify` skill (direct Matrix API, not OpenFang `channel_send`)
- **Skills:** zabbix-monitoring, proxmox-monitoring, juniper-monitoring, pbs-monitoring, truenas-monitoring, infrastructure-reference, email-notify, matrix-notify
- **Capabilities:** `tools = ["file_read", "file_write", "file_list", "shell_exec", "web_fetch", "memory_store", "memory_recall"]`, `memory_write = ["self.*", "shared.*"]`, `memory_read = ["*"]`. No `channel_send` — uses `matrix-notify` skill for outbound messages.
- **Execution model:** Agent-driven (not workflow). The investigation protocol has judgment calls that don't fit cleanly into a declarative pipeline. Can be formalized into a Workflow later if deterministic patterns emerge.

#### `inframon-patrol` — Nightly Sweep Agent
- **Type:** Regular agent (`builtin:chat`), triggered via cron job
- **Trigger:** Host-level cron or Docker cron container sends `POST /api/agents/{id}/message` with "Run nightly patrol" at 2 AM. **Not** an OpenFang Hand — Hands are compiled into the binary and cannot be added at runtime.
- **Purpose:** Proactive health checks across all infrastructure. Catches things Zabbix doesn't monitor or hasn't alerted on yet.
- **Notifications:** Posts reports to `#inframon-patrol` via `matrix-notify` skill. Cross-posts to `#inframon-alerts` only for critical findings.
- **Skills:** All monitoring skills + matrix-notify
- **Capabilities:** `tools = ["file_read", "file_write", "file_list", "shell_exec", "web_fetch", "memory_store", "memory_recall"]`, `memory_write = ["self.*", "shared.*"]`, `memory_read = ["*"]`. No `channel_send` — uses `matrix-notify` skill for outbound messages.
- **Key feature:** Uses OpenFang memory (`shared.patrol.*`) to store findings between runs. Tracks trends over time (storage growth, SMART error progression, sync lag patterns).

### Platform Constraints & Workarounds

| Constraint | Impact | Workaround |
|-----------|--------|------------|
| One `[channels.matrix]` section, one `default_agent` | Can't route different rooms to different agents | Interactive agent uses native Matrix channel. Triage and patrol send outbound via `matrix-notify` skill (direct Matrix Client-Server API). |
| `channel_send` can't target specific rooms | Agents can't choose which room to post to | `matrix-notify` skill accepts a `--room` parameter for room-targeted messages |
| Hands are compiled into the binary | Can't add custom Hands at runtime | Patrol is a regular agent triggered by external cron via the OpenFang API |
| OpenFang strips env vars from shell_exec | Skills can't read env vars normally | All skill scripts recover env from `/proc/1/environ` (existing pattern) |

### New Skill: `matrix-notify`

A new skill following the existing SKILL.md + scripts pattern:

```
skills/matrix-notify/
├── SKILL.md
└── scripts/
    └── matrix_notify.py    # argparse CLI, stdlib only (urllib)
```

**Interface:**
```bash
python3 /data/skills/matrix-notify/scripts/matrix_notify.py \
    --room "!roomid:matrix.org" \
    --message "Alert text here" \
    [--format markdown|plain]
```

**Env vars:** `MATRIX_ACCESS_TOKEN`, `MATRIX_HOMESERVER_URL` (defaults to `https://matrix.org`)

Uses the Matrix Client-Server API `PUT /_matrix/client/v3/rooms/{roomId}/send/m.room.message/{txnId}` directly. Stdlib-only (urllib.request), no dependencies.

### Patrol Checks

| Domain | Checks | Why Zabbix might miss it |
|--------|--------|------------------------|
| Proxmox | Node health, VM states, storage capacity, cluster quorum | Doesn't correlate (e.g., quorum risk if one more node drops) |
| PBS | Missing backups, failed verifications, sync lag to offsite, GC status | Zabbix doesn't monitor PBS |
| TrueNAS | Pool health, SMART trends, replication state, active alerts | SMART degradation is gradual — alerts after threshold, patrol catches the trend |
| Juniper | Interface error counters, alarms, environmental health | Incrementing error counters don't trigger until rate threshold |
| Zabbix | Unacknowledged problems, stale/orphan triggers | Meta-monitoring — making sure the monitoring itself isn't broken |

### Matrix Room Layout

| Room | Agent(s) | Mechanism | Purpose |
|------|----------|-----------|---------|
| `#inframon` | `inframon` | Native Matrix channel (`default_agent`) | Interactive chat with human operator |
| `#inframon-alerts` | `inframon-triage` (primary), `inframon-patrol` (critical cross-post) | `matrix-notify` skill | Alert investigations, critical findings. High-signal. |
| `#inframon-patrol` | `inframon-patrol` | `matrix-notify` skill | Nightly sweep reports. Audit trail. |

### Cross-Agent Knowledge

- **Agent-to-agent:** OpenFang native memory via `shared.*` namespace. Triage stores findings at `shared.triage.*`, patrol stores sweep results at `shared.patrol.*`. All agents can read all shared memory.
- **Trend data:** Patrol stores structured findings (e.g., `shared.patrol.storage.pve-r720 = "2026-03-12: 75%"`) so it can compare across runs. Memory decay (`decay_rate = 0.05`) may need tuning if trend data decays too fast — monitor and adjust.
- **Claude Code bridge:** Future work (beads issue im-0st — explore querying OpenFang agents via REST API or MCP server to pull agent memory into Claude Code sessions).

### Triage Investigation Protocol

Same 5-step protocol as today, but in a focused agent:

1. **Suppress check** — maintenance mode, known baselines (pve-z2 RAM ~96%), transient spikes, duplicate alerts
2. **Zabbix context** — `problem-details`, `host-items`, `history`
3. **Domain investigation** — route to the right skill based on host type
4. **Triage decision** — notify vs log-only, using agent judgment
5. **Act** — send to `#inframon-alerts` via `matrix-notify` if actionable, acknowledge in Zabbix, store findings in `shared.triage.*` memory

### Patrol Report Format

- **Clean patrol:** Brief summary — "All systems nominal. 4 PVE nodes healthy, 142 VMs running, PBS syncs current, no SMART changes."
- **Issues found:** Itemized findings with severity and recommended action. Critical items cross-posted to `#inframon-alerts`.
- **Trend tracking:** Compares current values to previous runs. Flags deviations (e.g., "pve-r720 storage 75%, up from 72% last week").
- **Error handling:** If patrol fails mid-run (LLM error, API timeout), it posts what it completed plus the error to `#inframon-patrol`. Partial results are still useful.

## Skills

No changes to the existing skill architecture. All skills remain as SKILL.md + scripts (portable, not OpenFang-specific). One new skill added:

| Skill | Status | Purpose |
|-------|--------|---------|
| `matrix-notify` | **New** | Room-targeted Matrix messaging via Client-Server API |
| All existing skills | Unchanged | Monitoring, email-notify, infrastructure-reference |

## Deployment

### New Files

| File | Purpose |
|------|---------|
| `openfang/agents/inframon/agent.toml` | Slimmed down — interactive only (~40 line prompt) |
| `openfang/agents/inframon-triage/agent.toml` | Alert investigation agent (~60 line prompt) |
| `openfang/agents/inframon-patrol/agent.toml` | Nightly sweep agent |
| `skills/matrix-notify/SKILL.md` | Matrix room notification skill metadata |
| `skills/matrix-notify/scripts/matrix_notify.py` | Matrix Client-Server API script |

### Config Changes

**config.toml:**
- `[channels.webhook]` → `default_agent = "inframon-triage"` (was `"inframon"`)
- `[channels.matrix]` → `default_agent = "inframon"` (unchanged)
- No other config changes needed

**docker-compose.openfang.yml:**
- Add `MATRIX_HOMESERVER_URL=https://matrix.org` to environment (for matrix-notify skill)
- Add cron mechanism for patrol trigger (either host crontab or a lightweight cron sidecar container)

### Cron Trigger for Patrol

The patrol agent is triggered externally since OpenFang Hands can't be added at runtime:

```bash
# Host crontab (or cron sidecar container)
# Port must match api_listen in config.toml (currently 50051, exposed as 4200 on host)
# Use container-internal port if running from within Docker, host-mapped port if from host crontab
0 2 * * * curl -s -X POST http://localhost:4200/api/agents/inframon-patrol/message \
  -H "Content-Type: application/json" \
  -d '{"message": "Run nightly patrol. Check all infrastructure and post report."}'
```

### Matrix Room Setup

Three rooms created on matrix.org. The @inframon:matrix.org bot joins all three.

| Room | Room ID |
|------|---------|
| `#inframon` (interactive) | `!PwgTYHCRXkvXzbgqpQ:matrix.org` |
| `#inframon-alerts` (triage) | `!wnxZoiPfVQuSIgJVvy:matrix.org` |
| `#inframon-patrol` (patrol) | `!GNBDVQhyXYYugtroNR:matrix.org` |

Room IDs recorded in the `infrastructure-reference` skill for agent access.

### Migration Strategy

Incremental, no big bang:

1. **Phase 1:** Create `matrix-notify` skill. Create Matrix rooms. Create `inframon-triage` agent. Change webhook `default_agent` to `inframon-triage`. Slim down `inframon` to interactive-only. Two agents running.
2. **Phase 2:** Create `inframon-patrol` agent. Set up cron trigger. Start with a simple nightly run, expand checks over time.
3. **Phase 3:** Tune. Adjust patrol schedule, refine triage prompt based on real alerts, tweak memory decay for trend data, build up patrol's trend knowledge.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Agent split | By execution mode (interactive/reactive/proactive) | Better than domain split — each mode has fundamentally different prompt and lifecycle needs |
| Triage execution | Agent-driven, not Workflow | Investigation protocol has judgment calls; can formalize later if deterministic patterns emerge |
| Skill format | Keep SKILL.md + scripts | Portable across agent frameworks; skill.toml is OpenFang-specific with no functional gain |
| Cross-agent memory | OpenFang native `shared.*` namespace | Zero setup, already wired up in capabilities |
| Patrol mechanism | Regular agent + external cron | OpenFang Hands are compiled into binary, can't add custom Hands at runtime |
| Matrix room targeting | New `matrix-notify` skill using Client-Server API | OpenFang's native `channel_send` can't target specific rooms; one `[channels.matrix]` section per config |
| Patrol schedule | Nightly at 2 AM | Catches overnight drift; can add more frequent runs later |
| Matrix rooms | Three separate rooms | Clean signal separation: alerts, patrol audit trail, human chat |
| Model config | Same for all agents (Qwen 35B, temp 0.2, Gemini Flash fallback) | Consistent behavior; triage's procedural prompt provides sufficient determinism without lower temperature |
