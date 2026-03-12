# Multi-Agent Architecture Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the monolith inframon agent into three specialized agents (interactive, triage, patrol) with room-targeted Matrix notifications.

**Architecture:** Three OpenFang agents split by execution mode. A new `matrix-notify` skill enables room-targeted messaging since OpenFang's native `channel_send` can't target specific rooms. Patrol agent is triggered by external cron since custom Hands can't be added at runtime.

**Tech Stack:** OpenFang agent OS, Python 3 (stdlib only), Matrix Client-Server API, TOML config

**Spec:** `docs/superpowers/specs/2026-03-12-multi-agent-architecture-design.md`

---

## Chunk 1: matrix-notify Skill

### Task 1: Create matrix-notify skill script

**Files:**
- Create: `skills/matrix-notify/scripts/matrix_notify.py`

This script sends messages to specific Matrix rooms using the Client-Server API. It follows the exact same pattern as `skills/email-notify/scripts/email_notify.py` — stdlib-only, argparse CLI, JSON output, env var recovery from `/proc/1/environ`.

- [ ] **Step 1: Create the script**

```python
#!/usr/bin/env python3
"""Send messages to specific Matrix rooms via Client-Server API.

Room-targeted notifications for infrastructure alerts and patrol reports.
Uses stdlib only (no third-party deps). Reads env vars from
/proc/1/environ to work around OpenFang's shell_exec sandbox.

Usage:
    python3 matrix_notify.py --room "!roomid:matrix.org" --message "Alert text"
    python3 matrix_notify.py --room "!roomid:matrix.org" --message "Alert text"
"""

import argparse
import json
import os
import sys
import time
import uuid
import urllib.error
import urllib.request
from pathlib import Path

# ── OpenFang env var recovery ─────────────────────────────────────
_proc_env = Path("/proc/1/environ")
if _proc_env.exists():
    for entry in _proc_env.read_bytes().split(b"\0"):
        if b"=" in entry:
            k, v = entry.decode("utf-8", errors="replace").split("=", 1)
            os.environ.setdefault(k, v)

# ── Matrix room ID constants ─────────────────────────────────────
ROOMS = {
    "inframon": "!PwgTYHCRXkvXzbgqpQ:matrix.org",
    "alerts": "!wnxZoiPfVQuSIgJVvy:matrix.org",
    "patrol": "!GNBDVQhyXYYugtroNR:matrix.org",
}


def send_message(room_id: str, message: str, homeserver: str, token: str) -> dict:
    # Matrix Client-Server API: PUT /_matrix/client/v3/rooms/{roomId}/send/m.room.message/{txnId}
    txn_id = f"{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
    url = f"{homeserver}/_matrix/client/v3/rooms/{room_id}/send/m.room.message/{txn_id}"

    # Most Matrix clients (Element, etc.) render markdown in the body field automatically
    body: dict = {"msgtype": "m.text", "body": message}

    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="PUT",
    )

    try:
        resp = urllib.request.urlopen(req, timeout=30)
        result = json.loads(resp.read().decode("utf-8"))
        return {"success": True, "event_id": result.get("event_id"), "room": room_id}
    except urllib.error.HTTPError as e:
        return {"success": False, "error": f"HTTP {e.code}: {e.read().decode()}"}
    except urllib.error.URLError as e:
        return {"success": False, "error": f"URL error: {e.reason}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="Send message to a Matrix room")
    parser.add_argument("--room", required=True,
                        help="Room ID (!xxx:matrix.org) or alias (inframon, alerts, patrol)")
    parser.add_argument("--message", required=True, help="Message text to send")
    args = parser.parse_args()

    token = os.environ.get("MATRIX_ACCESS_TOKEN")
    if not token:
        print(json.dumps({"success": False, "error": "MATRIX_ACCESS_TOKEN not set"}))
        sys.exit(1)

    homeserver = os.environ.get("MATRIX_HOMESERVER_URL", "https://matrix.org")

    # Resolve room alias to ID
    room_id = ROOMS.get(args.room, args.room)

    result = send_message(room_id, args.message, homeserver, token)
    print(json.dumps(result, indent=2))

    if not result["success"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify the script is syntactically valid**

Run: `python3 -c "import ast; ast.parse(open('skills/matrix-notify/scripts/matrix_notify.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add skills/matrix-notify/scripts/matrix_notify.py
git commit -m "feat: add matrix-notify skill script for room-targeted messaging"
```

---

### Task 2: Create matrix-notify SKILL.md

**Files:**
- Create: `skills/matrix-notify/SKILL.md`

- [ ] **Step 1: Create the SKILL.md**

```markdown
---
name: matrix-notify
description: Send messages to specific Matrix rooms. Used by triage and patrol agents to post to #inframon-alerts and #inframon-patrol rooms.
trigger_words:
  - notify
  - matrix
  - send message
  - post to room
  - alert room
  - patrol room
---

# Matrix Notify

Send messages to specific Matrix rooms via the Client-Server API. Bypasses OpenFang's `channel_send` which can't target specific rooms.

## Usage

```bash
python3 /data/skills/matrix-notify/scripts/matrix_notify.py --room <room> --message "text"
```

## Room Aliases

Built-in aliases for convenience (or use full room IDs):

| Alias | Room | Room ID |
|-------|------|---------|
| `inframon` | #inframon (interactive) | `!PwgTYHCRXkvXzbgqpQ:matrix.org` |
| `alerts` | #inframon-alerts (triage) | `!wnxZoiPfVQuSIgJVvy:matrix.org` |
| `patrol` | #inframon-patrol (patrol) | `!GNBDVQhyXYYugtroNR:matrix.org` |

## Examples

**Post alert investigation result:**
```bash
python3 /data/skills/matrix-notify/scripts/matrix_notify.py \
    --room alerts \
    --message "[WARNING] pve-r720 storage at 89% — recommend cleanup within 48h"
```

**Post patrol report:**
```bash
python3 /data/skills/matrix-notify/scripts/matrix_notify.py \
    --room patrol \
    --message "Nightly patrol complete. All systems nominal."
```

**Cross-post critical finding to alerts room:**
```bash
python3 /data/skills/matrix-notify/scripts/matrix_notify.py \
    --room alerts \
    --message "[CRITICAL] PBS offsite sync has not completed in 36 hours"
```

## Environment Variables

- `MATRIX_ACCESS_TOKEN` — Bot access token (required)
- `MATRIX_HOMESERVER_URL` — Homeserver URL (default: `https://matrix.org`)
```

- [ ] **Step 2: Commit**

```bash
git add skills/matrix-notify/SKILL.md
git commit -m "docs: add matrix-notify skill metadata and usage docs"
```

---

### Task 3: Add MATRIX_HOMESERVER_URL to docker-compose

**Files:**
- Modify: `docker-compose.openfang.yml`

- [ ] **Step 1: Add environment variable**

In the `environment:` section of `docker-compose.openfang.yml`, add after `MATRIX_ACCESS_TOKEN`:
```yaml
      - MATRIX_HOMESERVER_URL=https://matrix.org
```

- [ ] **Step 2: Commit**

```bash
git add docker-compose.openfang.yml
git commit -m "feat: add MATRIX_HOMESERVER_URL env var for matrix-notify skill"
```

---

### Task 4: Add Matrix room IDs to infrastructure-reference skill

**Files:**
- Modify: `skills/infrastructure-reference/SKILL.md`

- [ ] **Step 1: Add Matrix rooms section**

Add at the end of the file, after the `## Severity Levels (Zabbix)` section:

```markdown

## Matrix Rooms

| Room | Alias | Room ID | Purpose |
|------|-------|---------|---------|
| #inframon | `inframon` | `!PwgTYHCRXkvXzbgqpQ:matrix.org` | Interactive chat |
| #inframon-alerts | `alerts` | `!wnxZoiPfVQuSIgJVvy:matrix.org` | Alert investigations, critical findings |
| #inframon-patrol | `patrol` | `!GNBDVQhyXYYugtroNR:matrix.org` | Nightly sweep reports |

Bot account: `@inframon:matrix.org` on `matrix.org` homeserver.
```

- [ ] **Step 2: Commit**

```bash
git add skills/infrastructure-reference/SKILL.md
git commit -m "docs: add Matrix room IDs to infrastructure-reference skill"
```

---

## Chunk 2: Slim Down Interactive Agent

### Task 5: Rewrite inframon agent.toml for interactive-only

**Files:**
- Modify: `openfang/agents/inframon/agent.toml`

The current 190-line system prompt is replaced with a focused ~40-line conversational prompt. The investigation protocol, suppression rules, and notification routing are removed — those move to the triage agent.

- [ ] **Step 1: Back up the current agent.toml**

```bash
cp openfang/agents/inframon/agent.toml openfang/agents/inframon/agent.toml.monolith-backup
```

- [ ] **Step 2: Rewrite agent.toml**

Replace the entire file with:

```toml
name = "inframon"
version = "0.2.0"
description = "Interactive infrastructure assistant for BMIC — answers questions and runs ad-hoc investigations."
author = "kevinrussell"
module = "builtin:chat"
exec_policy = "full"

[model]
provider = "openrouter"
model = "qwen/qwen3.5-35b-a3b"
api_key_env = "OPENROUTER_API_KEY"
base_url = "https://openrouter.ai/api/v1"
max_tokens = 4096
temperature = 0.2
system_prompt = """You are **inframon**, an interactive infrastructure assistant for BMIC.

## Your Purpose

You help the operator answer questions about BMIC infrastructure: Proxmox cluster, Zabbix monitoring, Juniper switches, PBS backup servers, and TrueNAS storage.

You do NOT handle webhook alerts — that's the triage agent's job. You do NOT run scheduled patrols — that's the patrol agent's job. You focus on being a helpful, conversational assistant when the operator asks you something.

## Tools

All monitoring tools are shell scripts run via `shell_exec`. Each skill has a SKILL.md with full documentation.

**Zabbix** — `python3 /data/skills/zabbix-monitoring/scripts/zabbix_query.py <command>`
**Juniper** — `python3 /data/skills/juniper-monitoring/scripts/juniper_query.py <command> <host>`
**Proxmox** — `python3 /data/skills/proxmox-monitoring/scripts/proxmox_query.py <command>`
**PBS** — `python3 /data/skills/pbs-monitoring/scripts/pbs_query.py <command>`
**TrueNAS** — `uv run --directory /data/skills/truenas-monitoring python3 scripts/truenas_query.py <command>`
**Matrix Notify** — `python3 /data/skills/matrix-notify/scripts/matrix_notify.py --room <room> --message "text"`
**Email** — `python3 /data/skills/email-notify/scripts/email_notify.py --subject "..." --body "..."`

See each skill's SKILL.md for full command reference. See **infrastructure-reference** skill for host inventory, IPs, and severity levels.

## Cross-Agent Context

The triage and patrol agents store their findings in shared memory. You can recall their findings:
- `memory_recall("shared.triage.*")` — recent alert investigations
- `memory_recall("shared.patrol.*")` — recent patrol sweep results

## Working with Humans

- Be concise — operators need quick answers
- Show your work — what data you checked and why
- Ask before acting — only execute destructive commands with explicit approval
- Suggest next steps — what should the operator check or do next?
"""

[model.fallback]
provider = "openrouter"
model = "google/gemini-2.5-flash"
api_key_env = "OPENROUTER_API_KEY"
base_url = "https://openrouter.ai/api/v1"

[resources]
max_llm_tokens_per_hour = 500000
max_concurrent_tools = 5

[capabilities]
tools = [
    "file_read", "file_write", "file_list", "shell_exec", "web_fetch", "memory_store", "memory_recall", "channel_send",
]
workspace_paths = ["/data", "/usr/local/share/inframon"]
shell = [
    "/usr/local/share/inframon/scripts/*",
    "ssh *",
    "ping *",
    "python3 /data/skills/*",
    "python3 *",
    "uv run --directory /data/skills/* python3 *",
]
network = ["*"]
memory_read = ["*"]
memory_write = ["self.*", "shared.*"]
agent_spawn = false
```

- [ ] **Step 3: Verify TOML is valid**

Run: `python3 -c "import tomllib; tomllib.load(open('openfang/agents/inframon/agent.toml', 'rb')); print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add openfang/agents/inframon/agent.toml openfang/agents/inframon/agent.toml.monolith-backup
git commit -m "refactor: slim inframon agent to interactive-only (~40 line prompt)"
```

---

## Chunk 3: Triage Agent

### Task 6: Create inframon-triage agent.toml

**Files:**
- Create: `openfang/agents/inframon-triage/agent.toml`

This agent handles only Zabbix webhook alerts. Its system prompt contains the investigation protocol and suppression rules extracted from the monolith.

- [ ] **Step 1: Create agent directory**

```bash
mkdir -p openfang/agents/inframon-triage
```

- [ ] **Step 2: Create agent.toml**

```toml
name = "inframon-triage"
version = "0.1.0"
description = "Alert triage agent — investigates Zabbix webhook alerts and notifies via Matrix."
author = "kevinrussell"
module = "builtin:chat"
exec_policy = "full"

[model]
provider = "openrouter"
model = "qwen/qwen3.5-35b-a3b"
api_key_env = "OPENROUTER_API_KEY"
base_url = "https://openrouter.ai/api/v1"
max_tokens = 4096
temperature = 0.2
system_prompt = """You are **inframon-triage**, an alert investigation agent for BMIC infrastructure.

## Your Purpose

You receive Zabbix webhook alerts and investigate them autonomously. You follow a strict protocol, then either notify the operator (via Matrix #inframon-alerts room) or suppress the alert.

You do NOT handle human conversations — that's the interactive agent's job.

## Alert Investigation Protocol

When you receive a webhook alert (containing: host, severity, event_id, trigger_name, last_value):

**Step 1 — Check suppression rules.** If suppressed, store reason in shared memory and stop.

**Step 2 — Gather Zabbix context:**
- `python3 /data/skills/zabbix-monitoring/scripts/zabbix_query.py problem-details <event_id>`
- `python3 /data/skills/zabbix-monitoring/scripts/zabbix_query.py host-items <host>`
- `python3 /data/skills/zabbix-monitoring/scripts/zabbix_query.py history <itemid>`

**Step 3 — Investigate with domain skills:**
- Proxmox host → `python3 /data/skills/proxmox-monitoring/scripts/proxmox_query.py node-status <node>`
- Network device → `python3 /data/skills/juniper-monitoring/scripts/juniper_query.py interfaces <host>`
- Backup issue → `python3 /data/skills/pbs-monitoring/scripts/pbs_query.py <command>`
- Storage issue → `uv run --directory /data/skills/truenas-monitoring python3 scripts/truenas_query.py <command>`

**Step 4 — Triage decision:**
- **Notify** (via Matrix + email backup): confirmed failures, degraded services, capacity warnings, anything requiring human action
- **Log only** (via shared memory): transient blips that resolved, expected behavior, informational events
- Use your judgment — a low-severity alert that reveals a real problem should notify; a high-severity alert caused by a flapping sensor should not

**Step 5 — Act:**
- Notify: `python3 /data/skills/matrix-notify/scripts/matrix_notify.py --room alerts --message "[SEVERITY] Finding summary"`
- Email backup: `python3 /data/skills/email-notify/scripts/email_notify.py --subject "[SEVERITY] Issue" --body "Details"`
- Acknowledge: `python3 /data/skills/zabbix-monitoring/scripts/zabbix_query.py acknowledge <event_id> --message "investigation summary"`
- Store findings: `memory_store("shared.triage.<host>.<event_id>", "summary of findings")`

## Suppression Rules (Do NOT Notify)

- Transient CPU/RAM spikes that resolve within same check cycle
- Duplicate alerts already notified in current cycle
- Hosts in Zabbix maintenance mode
- pve-z2 RAM at ~96% (steady-state baseline — only alert above 98%)
- pve-r620 — currently marked active but may show intermittent issues

When suppressing, always store reason: `memory_store("shared.triage.suppressed.<event_id>", "reason")`

## Severity-to-Notification Mapping

See **infrastructure-reference** skill for full severity definitions and host inventory.

| Severity | Matrix Prefix | Email? |
|----------|--------------|--------|
| 5 Disaster | [CRITICAL] | Yes |
| 4 High | [CRITICAL] | Yes |
| 3 Average | [WARNING] | No (Matrix only) |
| 2 Warning | [INFO] | No |
| 1 Info | Suppress | No |
"""

[model.fallback]
provider = "openrouter"
model = "google/gemini-2.5-flash"
api_key_env = "OPENROUTER_API_KEY"
base_url = "https://openrouter.ai/api/v1"

[resources]
max_llm_tokens_per_hour = 500000
max_concurrent_tools = 5

[capabilities]
tools = [
    "file_read", "file_write", "file_list", "shell_exec", "web_fetch", "memory_store", "memory_recall",
]
workspace_paths = ["/data", "/usr/local/share/inframon"]
shell = [
    "/usr/local/share/inframon/scripts/*",
    "python3 /data/skills/*",
    "python3 *",
    "uv run --directory /data/skills/* python3 *",
]
network = ["*"]
memory_read = ["*"]
memory_write = ["self.*", "shared.triage.*"]
agent_spawn = false
```

- [ ] **Step 3: Verify TOML is valid**

Run: `python3 -c "import tomllib; tomllib.load(open('openfang/agents/inframon-triage/agent.toml', 'rb')); print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add openfang/agents/inframon-triage/agent.toml
git commit -m "feat: add inframon-triage agent for Zabbix webhook alert handling"
```

---

### Task 7: Point webhook channel at triage agent

**Files:**
- Modify: `openfang/config.toml`

- [ ] **Step 1: Change webhook default_agent**

In `openfang/config.toml`, change:
```toml
[channels.webhook]
default_agent = "inframon"
```
to:
```toml
[channels.webhook]
default_agent = "inframon-triage"
```

- [ ] **Step 2: Commit**

```bash
git add openfang/config.toml
git commit -m "feat: route webhook alerts to inframon-triage agent"
```

---

## Chunk 4: Patrol Agent

### Task 8: Create inframon-patrol agent.toml

**Files:**
- Create: `openfang/agents/inframon-patrol/agent.toml`

This agent runs proactive health checks when triggered by an external cron job. It checks all infrastructure domains and posts a report to `#inframon-patrol`, cross-posting critical findings to `#inframon-alerts`.

- [ ] **Step 1: Create agent directory**

```bash
mkdir -p openfang/agents/inframon-patrol
```

- [ ] **Step 2: Create agent.toml**

```toml
name = "inframon-patrol"
version = "0.1.0"
description = "Nightly patrol agent — proactive health checks across all BMIC infrastructure."
author = "kevinrussell"
module = "builtin:chat"
exec_policy = "full"

[model]
provider = "openrouter"
model = "qwen/qwen3.5-35b-a3b"
api_key_env = "OPENROUTER_API_KEY"
base_url = "https://openrouter.ai/api/v1"
max_tokens = 4096
temperature = 0.2
system_prompt = """You are **inframon-patrol**, a proactive infrastructure health checker for BMIC.

## Your Purpose

When triggered, you run a comprehensive sweep of all BMIC infrastructure and post a report. You catch issues that Zabbix might miss — trends, correlations, things that haven't hit alert thresholds yet.

## Patrol Procedure

Run ALL checks below in order, then compile a report.

### 1. Proxmox Cluster
```
python3 /data/skills/proxmox-monitoring/scripts/proxmox_query.py cluster-status
python3 /data/skills/proxmox-monitoring/scripts/proxmox_query.py nodes
python3 /data/skills/proxmox-monitoring/scripts/proxmox_query.py vms
python3 /data/skills/proxmox-monitoring/scripts/proxmox_query.py storage
```
Check: All nodes online? Quorum healthy? Any VM in unexpected state? Storage capacity trending high?

### 2. PBS Backup Health
```
python3 /data/skills/pbs-monitoring/scripts/pbs_query.py datastores
python3 /data/skills/pbs-monitoring/scripts/pbs_query.py missing-backups --days 2
python3 /data/skills/pbs-monitoring/scripts/pbs_query.py verify-jobs
python3 /data/skills/pbs-monitoring/scripts/pbs_query.py sync-jobs
python3 /data/skills/pbs-monitoring/scripts/pbs_query.py gc-status
```
Check: Any VMs missing backups? Verifications failing? Offsite sync current? GC running?

### 3. TrueNAS Storage
```
uv run --directory /data/skills/truenas-monitoring python3 scripts/truenas_query.py pools
uv run --directory /data/skills/truenas-monitoring python3 scripts/truenas_query.py alerts
uv run --directory /data/skills/truenas-monitoring python3 scripts/truenas_query.py disks
uv run --directory /data/skills/truenas-monitoring python3 scripts/truenas_query.py replication
```
Check: Pool health? SMART errors increasing? Active alerts? Replication current?

### 4. Network Switches
```
python3 /data/skills/juniper-monitoring/scripts/juniper_query.py alarms ex3400
python3 /data/skills/juniper-monitoring/scripts/juniper_query.py alarms ex2300
python3 /data/skills/juniper-monitoring/scripts/juniper_query.py environment ex3400
python3 /data/skills/juniper-monitoring/scripts/juniper_query.py environment ex2300
```
Check: Any active alarms? Environmental health OK? Interface errors?

### 5. Zabbix Meta-Check
```
python3 /data/skills/zabbix-monitoring/scripts/zabbix_query.py unacknowledged-problems
python3 /data/skills/zabbix-monitoring/scripts/zabbix_query.py active-problems --severity-min 2
```
Check: Unacknowledged problems lingering? Any active issues that were missed?

## Trend Tracking

After gathering data, compare with previous patrol findings:
- `memory_recall("shared.patrol.*")` — previous results
- Store current findings: `memory_store("shared.patrol.<domain>.<metric>", "YYYY-MM-DD: value")`

Flag any concerning trends (storage growing, error counts increasing, sync lag worsening).

## Report Format

Compile ALL findings into a single report and post to the patrol room:
```
python3 /data/skills/matrix-notify/scripts/matrix_notify.py --room patrol --message "<report>"
```

**Report structure:**
```
BMIC Infrastructure Patrol — YYYY-MM-DD HH:MM

PROXMOX: [OK|WARN|CRITICAL] — <summary>
PBS: [OK|WARN|CRITICAL] — <summary>
TRUENAS: [OK|WARN|CRITICAL] — <summary>
NETWORK: [OK|WARN|CRITICAL] — <summary>
ZABBIX: [OK|WARN|CRITICAL] — <summary>

TRENDS:
- <any notable changes from previous patrols>

ACTIONS NEEDED:
- <anything requiring human attention, or "None">
```

## Critical Cross-Post Rule

If ANY domain shows CRITICAL status, ALSO post to the alerts room:
```
python3 /data/skills/matrix-notify/scripts/matrix_notify.py --room alerts --message "[CRITICAL] Patrol found: <issue>"
```

## Error Handling

If a check fails (timeout, API error), note it in the report and continue with remaining checks. Partial results are still useful. Do NOT stop the patrol because one check failed.
"""

[model.fallback]
provider = "openrouter"
model = "google/gemini-2.5-flash"
api_key_env = "OPENROUTER_API_KEY"
base_url = "https://openrouter.ai/api/v1"

[resources]
max_llm_tokens_per_hour = 500000
max_concurrent_tools = 5

[capabilities]
tools = [
    "file_read", "file_write", "file_list", "shell_exec", "web_fetch", "memory_store", "memory_recall",
]
workspace_paths = ["/data", "/usr/local/share/inframon"]
shell = [
    "/usr/local/share/inframon/scripts/*",
    "python3 /data/skills/*",
    "python3 *",
    "uv run --directory /data/skills/* python3 *",
]
network = ["*"]
memory_read = ["*"]
memory_write = ["self.*", "shared.patrol.*"]
agent_spawn = false
```

- [ ] **Step 3: Verify TOML is valid**

Run: `python3 -c "import tomllib; tomllib.load(open('openfang/agents/inframon-patrol/agent.toml', 'rb')); print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add openfang/agents/inframon-patrol/agent.toml
git commit -m "feat: add inframon-patrol agent for nightly infrastructure sweeps"
```

---

### Task 9: Configure patrol schedule

OpenFang may support scheduling custom agents/Hands via the UI. After deploying all three agents:

- [ ] **Step 1: Deploy and verify all agents are running (see Task 11)**

- [ ] **Step 2: Configure schedule via OpenFang UI**

Open the OpenFang dashboard and configure a nightly schedule for `inframon-patrol`. Kevin will create this via the UI — inspect the resulting config to understand the format.

- [ ] **Step 3: Verify the schedule fires**

If OpenFang's native scheduling works, the patrol agent should activate on schedule. If not, fall back to a host crontab entry:

```bash
# Fallback: host crontab trigger
cat > openfang/scripts/trigger-patrol.sh << 'EOF'
#!/bin/bash
curl -sf -X POST http://localhost:4200/api/agents/inframon-patrol/message \
    -H "Content-Type: application/json" \
    -d '{"message": "Run nightly patrol. Check all infrastructure and post report."}' \
    >> /tmp/patrol-cron.log 2>&1
EOF
chmod +x openfang/scripts/trigger-patrol.sh
(crontab -l 2>/dev/null; echo "0 2 * * * $(pwd)/openfang/scripts/trigger-patrol.sh") | crontab -
```

- [ ] **Step 4: Commit any schedule config changes**

```bash
git add -A && git commit -m "feat: configure patrol schedule"
```

---

## Chunk 5: Final Config & Verification

### Task 10: Update CLAUDE.md with new architecture

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update Architecture section**

In the `## Architecture` section of `CLAUDE.md`, replace:
```
- **Runtime:** OpenFang agent OS in Docker (`docker-compose.openfang.yml`)
```
with:
```
- **Runtime:** OpenFang agent OS in Docker (`docker-compose.openfang.yml`)
- **Agents:** Three specialized agents — `inframon` (interactive chat), `inframon-triage` (webhook alert handling), `inframon-patrol` (nightly health sweeps)
```

- [ ] **Step 2: Update Key Files table**

Add to the Key Files table:
```
| `openfang/agents/inframon-triage/agent.toml` | Triage agent: webhook alert investigation |
| `openfang/agents/inframon-patrol/agent.toml` | Patrol agent: nightly proactive health sweeps |
| `skills/matrix-notify/` | Room-targeted Matrix messaging skill |
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with multi-agent architecture"
```

---

### Task 11: Build and verify deployment

- [ ] **Step 1: Build the container**

Run: `docker compose -f docker-compose.openfang.yml build`
Expected: Successful build with no errors

- [ ] **Step 2: Start the stack**

Run: `docker compose -f docker-compose.openfang.yml up -d`
Expected: `bmic-inframon-openfang` container starts

- [ ] **Step 3: Verify health**

Run: `curl -sf http://localhost:4200/api/health`
Expected: Health check passes

- [ ] **Step 4: Verify all three agents are registered**

Run: `curl -sf http://localhost:4200/api/agents | python3 -m json.tool`
Expected: Shows `inframon`, `inframon-triage`, and `inframon-patrol` agents

- [ ] **Step 5: Test matrix-notify skill manually**

Run from inside the container:
```bash
docker exec bmic-inframon-openfang python3 /data/skills/matrix-notify/scripts/matrix_notify.py \
    --room patrol --message "Test message from matrix-notify skill"
```
Expected: `{"success": true, "event_id": "...", "room": "!GNBDVQhyXYYugtroNR:matrix.org"}` and message appears in #inframon-patrol Matrix room

- [ ] **Step 6: Test triage agent with a simulated webhook**

```bash
curl -sf -X POST http://localhost:4200/api/agents/inframon-triage/message \
    -H "Content-Type: application/json" \
    -d '{"message": "Test alert: host=pve-z2, severity=3, event_id=test123, trigger_name=test trigger, last_value=95%"}'
```
Expected: Triage agent investigates and posts to #inframon-alerts

- [ ] **Step 7: Test patrol agent manually**

```bash
curl -sf -X POST http://localhost:4200/api/agents/inframon-patrol/message \
    -H "Content-Type: application/json" \
    -d '{"message": "Run nightly patrol. Check all infrastructure and post report."}'
```
Expected: Patrol agent runs all checks and posts report to #inframon-patrol

- [ ] **Step 8: Test interactive agent via Matrix**

Send a message in #inframon Matrix room: "What's the cluster status?"
Expected: `inframon` agent responds with Proxmox cluster info

- [ ] **Step 9: Commit any fixes and push**

```bash
git push
```
