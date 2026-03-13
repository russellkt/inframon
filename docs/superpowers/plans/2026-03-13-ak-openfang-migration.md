# ak Maintenance Migration to OpenFang Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move all `ak` knowledge maintenance jobs from Mac mini launchd to OpenFang Hands on VM101, leaving zero scheduled processes on dev machines.

**Architecture:** Four OpenFang agents (ak-enrich, ak-tidy, ak-snapshot, ak-digest) run on VM101 using the `ak` CLI against `pg-ak` (Tailscale). An `ak-maintenance` Workflow chains them every 6 hours. `ak-enrich` also fires immediately when the Mac mini session-end hook POSTs to the OpenFang API. `ak-digest` fires via ContentMatch trigger after each Workflow run.

**Tech Stack:** OpenFang agents (TOML), Go (`go install` for `ak` binary), PostgreSQL (pg-ak at 100.127.176.3:5432 via Tailscale), Gemini 2.5 Flash via OpenRouter BYOK, OpenFang Workflow/Trigger/Cron API.

---

## Key Facts (read before implementing)

- **OpenFang strips env vars from shell_exec** — every script must recover from `/proc/1/environ`. Use the pattern in CLAUDE.md.
- **Workflows/Triggers/Cron are runtime registrations** — not in config.toml. Register via `openfang workflow create <file>` and API calls after daemon starts.
- **`[schedule]` block in agent.toml is NOT supported** — agents self-schedule using the `schedule_create` tool in their system prompt (first-run check pattern).
- **Webhook channel (port 8460) routes to inframon-triage** — to trigger ak-enrich from the Mac mini, POST directly to the OpenFang REST API: `POST /api/agents/ak-enrich/message`.
- **OpenFang API default port: 4200** — internal to Docker; expose via docker-compose if Mac mini needs to reach it.
- **`ak` commands for agents:** `ak enrich <project>`, `ak tidy <project> --apply`, `ak snapshot <project>`, `ak dedup <project> --merge`, `ak embed-backfill`, `ak link-detect`, `ak stats`.
- **CronSchedule kinds:** `every` (every_secs), `at` (exact UTC), `cron` (5-field expression).
- **CronAction kinds:** `agent_turn` (send message to agent), `workflow_run` (run workflow by name/ID).
- **ContentMatch trigger pattern JSON:** `{"type": "content_match", "substring": "ak-maintenance complete"}`.

---

## File Map

| Action | Path |
|--------|------|
| Modify | `Dockerfile.openfang` |
| Modify | `docker-compose.openfang.yml` |
| Create | `openfang/agents/ak-enrich/agent.toml` |
| Create | `openfang/agents/ak-tidy/agent.toml` |
| Create | `openfang/agents/ak-snapshot/agent.toml` |
| Create | `openfang/agents/ak-digest/agent.toml` |
| Create | `openfang/workflows/ak-maintenance.json` |
| Create | `scripts/setup-ak-openfang.sh` |
| Modify | `~/.claude/settings.json` (SessionEnd hook) |
| Delete | `~/Library/LaunchAgents/com.agent-knowledge.ingest.plist` |
| Delete | `~/Library/LaunchAgents/com.agent-knowledge.snapshot.plist` |

---

## Chunk 1: Docker — Go + ak Binary + Env Vars

### Task 1: Add Go and ak to Dockerfile

**Files:**
- Modify: `Dockerfile.openfang`

- [ ] **Step 1: Read current Dockerfile**

```bash
cat Dockerfile.openfang
```

- [ ] **Step 2: Add Go install + ak binary after the uv install block**

Add after the `ENV PATH="/root/.local/bin:${PATH}"` line:

```dockerfile
# Install Go for ak CLI
RUN curl -fsSL https://go.dev/dl/go1.23.4.linux-amd64.tar.gz -o /tmp/go.tar.gz \
    && tar -C /usr/local -xzf /tmp/go.tar.gz \
    && rm /tmp/go.tar.gz

ENV PATH="/usr/local/go/bin:/root/go/bin:${PATH}"

# Install ak knowledge CLI
RUN go install github.com/russellkt/agent-knowledge/cmd/ak@latest
```

- [ ] **Step 3: Verify ak is on PATH in Dockerfile**

The `go install` puts binaries in `/root/go/bin`. Confirm `ENV PATH` includes `/root/go/bin`.

- [ ] **Step 4: Commit**

```bash
git add Dockerfile.openfang
git commit -m "feat: install Go and ak CLI in OpenFang Docker image"
```

---

### Task 2: Add ak env vars to docker-compose

**Files:**
- Modify: `docker-compose.openfang.yml`

- [ ] **Step 1: Read current docker-compose environment block**

```bash
grep -A20 "environment:" docker-compose.openfang.yml
```

- [ ] **Step 2: Add ak env vars to the environment section**

```yaml
- AK_DB_URL=${AK_DB_URL}
- AK_LLM_URL=${AK_LLM_URL}
- AK_LLM_MODEL=${AK_LLM_MODEL}
- AK_LLM_API_KEY=${OPENROUTER_API_KEY}
```

- [ ] **Step 3: Expose port 4200 for Mac mini API access**

In the `ports` section, add:
```yaml
- "4200:4200"
```
(This allows the Mac mini session-end hook to POST to `http://10.10.1.127:4200/api/...`)

- [ ] **Step 4: Add ak vars to .env**

```bash
# In .env (already has OPENROUTER_API_KEY — AK_LLM_API_KEY maps to it)
AK_DB_URL=postgres://ak:IVktJYgnzfvp6Eo0ZMxed1kt@100.127.176.3:5432/agent_knowledge
AK_LLM_URL=https://openrouter.ai/api/v1
AK_LLM_MODEL=google/gemini-2.5-flash
```

- [ ] **Step 5: Commit**

```bash
git add docker-compose.openfang.yml .env.example
git commit -m "feat: add ak env vars and expose port 4200 in docker-compose"
```

---

### Task 3: Test build

- [ ] **Step 1: Build the image**

```bash
docker compose -f docker-compose.openfang.yml build 2>&1 | tail -20
```
Expected: `Successfully built ...` — no errors.

- [ ] **Step 2: Verify ak binary is present**

```bash
docker compose -f docker-compose.openfang.yml run --rm openfang ak --version
```
Expected: prints `ak version X.Y.Z`.

---

## Chunk 2: ak Agent Definitions

### Task 4: Create ak-enrich agent

**Files:**
- Create: `openfang/agents/ak-enrich/agent.toml`

- [ ] **Step 1: Create directory**

```bash
mkdir -p openfang/agents/ak-enrich
```

- [ ] **Step 2: Write agent.toml**

```toml
name = "ak-enrich"
version = "0.1.0"
description = "Enriches ak knowledge base — re-categorizes memories, improves summaries, fills metadata gaps."
author = "kevinrussell"
module = "builtin:chat"
exec_policy = "full"

[model]
provider = "openrouter"
model = "google/gemini-2.5-flash"
api_key_env = "OPENROUTER_API_KEY"
base_url = "https://openrouter.ai/api/v1"
max_tokens = 4096
temperature = 0.2
system_prompt = """You are ak-enrich, a knowledge base enrichment agent. You improve memory quality in the ak PostgreSQL database by fixing categories and improving content.

## CRITICAL: Environment Setup

Before using `ak`, ensure env vars are loaded. Run this Python snippet once:
```
python3 -c "
import os
from pathlib import Path
p = Path('/proc/1/environ')
if p.exists():
    for e in p.read_bytes().split(b'\x00'):
        if b'=' in e:
            k, v = e.decode('utf-8', errors='replace').split('=', 1)
            os.environ.setdefault(k, v)
print('AK_DB_URL set:', bool(os.environ.get('AK_DB_URL')))
"
```

## Self-Scheduling (First Run Only)

Check if your schedule already exists:
```
schedule_list
```
If no schedule named "ak-enrich-2h" exists, create it:
```
schedule_create("ak-enrich-2h", {"kind": "cron", "expr": "0 */2 * * *"}, {"kind": "agent_turn", "message": "Run enrichment on all projects"}, {"kind": "none"})
```

## Enrichment Workflow

1. Get project list: `shell_exec("ak stats 2>/dev/null")`
2. For each project, run: `shell_exec("ak enrich <project> 2>/dev/null")`
3. Skip projects starting with `-`
4. Report: how many projects enriched, how many memories changed

## Categories
- `decision` — "chose", "decided", "went with"
- `pattern` — "always", "never", "best practice"
- `error_fix` — "error", "fix", "bug", "workaround"
- `architecture` — "connects to", "system design", "flow"
- `note` — fallback only

## Output
Print a brief summary: `Enrichment complete: N projects processed, M memories updated.`
If nothing changed, just print: `Enrichment complete: no changes needed.`
"""

[model.fallback]
provider = "openrouter"
model = "google/gemini-2.5-flash"
api_key_env = "OPENROUTER_API_KEY"
base_url = "https://openrouter.ai/api/v1"

[resources]
max_llm_tokens_per_hour = 200000
max_concurrent_tools = 3

[capabilities]
tools = ["shell_exec", "memory_store", "memory_recall", "schedule_create", "schedule_list"]
shell = ["python3 *", "ak *"]
network = ["100.127.176.3"]
memory_read = ["self.*"]
memory_write = ["self.*"]
```

- [ ] **Step 3: Commit**

```bash
git add openfang/agents/ak-enrich/
git commit -m "feat: add ak-enrich OpenFang agent"
```

---

### Task 5: Create ak-tidy agent

**Files:**
- Create: `openfang/agents/ak-tidy/agent.toml`

- [ ] **Step 1: Create directory and write agent.toml**

```bash
mkdir -p openfang/agents/ak-tidy
```

```toml
name = "ak-tidy"
version = "0.1.0"
description = "Cleans ak knowledge base — deduplicates, removes stale memories, fixes miscategorizations."
author = "kevinrussell"
module = "builtin:chat"
exec_policy = "full"

[model]
provider = "openrouter"
model = "google/gemini-2.5-flash"
api_key_env = "OPENROUTER_API_KEY"
base_url = "https://openrouter.ai/api/v1"
max_tokens = 4096
temperature = 0.2
system_prompt = """You are ak-tidy, a knowledge base quality agent. You maintain the ak PostgreSQL database by removing duplicates and low-quality entries.

## CRITICAL: Environment Setup

Before using `ak`, run this once:
```
python3 -c "
import os
from pathlib import Path
p = Path('/proc/1/environ')
if p.exists():
    for e in p.read_bytes().split(b'\x00'):
        if b'=' in e:
            k, v = e.decode('utf-8', errors='replace').split('=', 1)
            os.environ.setdefault(k, v)
print('AK_DB_URL set:', bool(os.environ.get('AK_DB_URL')))
"
```

## Tidy Workflow

1. Get project list: `shell_exec("ak stats 2>/dev/null")`
2. For each project:
   a. Dedup: `shell_exec("ak dedup <project> --merge 2>/dev/null")`
   b. Tidy: `shell_exec("ak tidy <project> --apply 2>/dev/null")`
3. Skip projects starting with `-`
4. Run link detection: `shell_exec("ak link-detect 2>/dev/null")`

## Output
Print: `Tidy complete: N projects processed.`
Be conservative — `ak tidy --apply` already handles the decisions. Report what it changed.
"""

[model.fallback]
provider = "openrouter"
model = "google/gemini-2.5-flash"
api_key_env = "OPENROUTER_API_KEY"
base_url = "https://openrouter.ai/api/v1"

[resources]
max_llm_tokens_per_hour = 200000
max_concurrent_tools = 3

[capabilities]
tools = ["shell_exec", "memory_store", "memory_recall"]
shell = ["python3 *", "ak *"]
network = ["100.127.176.3"]
memory_read = ["self.*"]
memory_write = ["self.*"]
```

- [ ] **Step 2: Commit**

```bash
git add openfang/agents/ak-tidy/
git commit -m "feat: add ak-tidy OpenFang agent"
```

---

### Task 6: Create ak-snapshot agent

**Files:**
- Create: `openfang/agents/ak-snapshot/agent.toml`

- [ ] **Step 1: Create directory and write agent.toml**

```bash
mkdir -p openfang/agents/ak-snapshot
```

```toml
name = "ak-snapshot"
version = "0.1.0"
description = "Regenerates ak project snapshots and runs embed-backfill for vector search."
author = "kevinrussell"
module = "builtin:chat"
exec_policy = "full"

[model]
provider = "openrouter"
model = "google/gemini-2.5-flash"
api_key_env = "OPENROUTER_API_KEY"
base_url = "https://openrouter.ai/api/v1"
max_tokens = 2048
temperature = 0.2
system_prompt = """You are ak-snapshot, a knowledge maintenance agent. You keep project snapshots and embeddings current.

## CRITICAL: Environment Setup

Before using `ak`, run this once:
```
python3 -c "
import os
from pathlib import Path
p = Path('/proc/1/environ')
if p.exists():
    for e in p.read_bytes().split(b'\x00'):
        if b'=' in e:
            k, v = e.decode('utf-8', errors='replace').split('=', 1)
            os.environ.setdefault(k, v)
print('AK_DB_URL set:', bool(os.environ.get('AK_DB_URL')))
"
```

## Snapshot Workflow

1. Run embedding backfill first: `shell_exec("ak embed-backfill 2>/dev/null")`
2. Get project list: `shell_exec("ak stats 2>/dev/null")`
3. For each project, regenerate snapshot: `shell_exec("ak snapshot <project> 2>/dev/null")`
4. Skip projects starting with `-`

## Output
Print: `Snapshots complete: N generated, M cached (no changes).`
Then print exactly: `ak-maintenance complete`
(This triggers the ak-digest agent via ContentMatch.)
"""

[model.fallback]
provider = "openrouter"
model = "google/gemini-2.5-flash"
api_key_env = "OPENROUTER_API_KEY"
base_url = "https://openrouter.ai/api/v1"

[resources]
max_llm_tokens_per_hour = 300000
max_concurrent_tools = 3

[capabilities]
tools = ["shell_exec", "memory_store", "memory_recall"]
shell = ["python3 *", "ak *"]
network = ["100.127.176.3"]
memory_read = ["self.*"]
memory_write = ["self.*"]
```

- [ ] **Step 2: Commit**

```bash
git add openfang/agents/ak-snapshot/
git commit -m "feat: add ak-snapshot OpenFang agent"
```

---

### Task 7: Create ak-digest agent

**Files:**
- Create: `openfang/agents/ak-digest/agent.toml`

- [ ] **Step 1: Create directory and write agent.toml**

```bash
mkdir -p openfang/agents/ak-digest
```

```toml
name = "ak-digest"
version = "0.1.0"
description = "Cross-project knowledge synthesis — generates summaries, detects contradictions, identifies patterns."
author = "kevinrussell"
module = "builtin:chat"
exec_policy = "full"

[model]
provider = "openrouter"
model = "google/gemini-2.5-flash"
api_key_env = "OPENROUTER_API_KEY"
base_url = "https://openrouter.ai/api/v1"
max_tokens = 8192
temperature = 0.3
system_prompt = """You are ak-digest, a cross-project knowledge synthesis agent. You analyze the ak database to produce insights.

## CRITICAL: Environment Setup

Before using `ak`, run this once:
```
python3 -c "
import os
from pathlib import Path
p = Path('/proc/1/environ')
if p.exists():
    for e in p.read_bytes().split(b'\x00'):
        if b'=' in e:
            k, v = e.decode('utf-8', errors='replace').split('=', 1)
            os.environ.setdefault(k, v)
print('AK_DB_URL set:', bool(os.environ.get('AK_DB_URL')))
"
```

## Digest Workflow

1. Get recent sessions: `shell_exec("ak sessions --limit 50 2>/dev/null")`
2. Get stats: `shell_exec("ak stats 2>/dev/null")`
3. For active projects (with recent sessions), run: `shell_exec("ak context <project> 2>/dev/null")`
4. Identify:
   - Notable decisions made recently
   - Patterns appearing across multiple projects
   - Contradictions between memories
   - Cross-project connections

## Output Format

```markdown
# Knowledge Digest — <date>

## Active Projects
- <project>: <N memories, summary>

## Notable Decisions
- <decision> (project: <name>, ID: <id>)

## Cross-Project Patterns
- <pattern seen in multiple projects>

## Contradictions
- Memory #X says ... but Memory #Y says ... (suggest keeping #Y, newer)
```

Post digest to logs for now (Matrix room #ak-digest to be configured later).
Store: `memory_store("self.last_digest", "<date>")`
"""

[model.fallback]
provider = "openrouter"
model = "google/gemini-2.5-flash"
api_key_env = "OPENROUTER_API_KEY"
base_url = "https://openrouter.ai/api/v1"

[resources]
max_llm_tokens_per_hour = 400000
max_concurrent_tools = 3

[capabilities]
tools = ["shell_exec", "memory_store", "memory_recall"]
shell = ["python3 *", "ak *"]
network = ["100.127.176.3"]
memory_read = ["self.*"]
memory_write = ["self.*"]
```

- [ ] **Step 2: Commit**

```bash
git add openfang/agents/ak-digest/
git commit -m "feat: add ak-digest OpenFang agent"
```

---

## Chunk 3: Workflow + Setup Script

### Task 8: Create ak-maintenance workflow JSON

**Files:**
- Create: `openfang/workflows/ak-maintenance.json`

- [ ] **Step 1: Create workflows directory**

```bash
mkdir -p openfang/workflows
```

- [ ] **Step 2: Write workflow JSON**

```json
{
  "name": "ak-maintenance",
  "description": "Full ak knowledge base maintenance pipeline: embed-backfill, dedup, tidy, enrich, snapshot, link-detect. Runs every 6h. Final step triggers ak-digest via ContentMatch.",
  "steps": [
    {
      "name": "embed-backfill-and-tidy",
      "agent_name": "ak-tidy",
      "prompt": "Run full tidy pipeline: embed-backfill, dedup all projects, tidy all projects, link-detect.",
      "mode": "sequential",
      "timeout_secs": 600,
      "error_mode": "skip"
    },
    {
      "name": "enrich",
      "agent_name": "ak-enrich",
      "prompt": "Run enrichment on all projects. Fix miscategorized memories.",
      "mode": "sequential",
      "timeout_secs": 600,
      "error_mode": "skip"
    },
    {
      "name": "snapshot",
      "agent_name": "ak-snapshot",
      "prompt": "Run embed-backfill and regenerate all project snapshots. End your output with 'ak-maintenance complete'.",
      "mode": "sequential",
      "timeout_secs": 600,
      "error_mode": "skip"
    }
  ]
}
```

Note: The final step (ak-snapshot) outputs `ak-maintenance complete` which fires the ContentMatch trigger for ak-digest.

- [ ] **Step 3: Commit**

```bash
git add openfang/workflows/
git commit -m "feat: add ak-maintenance workflow definition"
```

---

### Task 9: Create setup script

**Files:**
- Create: `scripts/setup-ak-openfang.sh`

This script registers the workflow, cron job, and digest trigger with a running OpenFang daemon. Run once after first deploy (or after container recreate).

- [ ] **Step 1: Write setup script**

```bash
mkdir -p scripts
```

```bash
#!/bin/bash
# scripts/setup-ak-openfang.sh
# One-time registration of ak-maintenance workflow, cron, and digest trigger.
# Run against the OpenFang daemon on VM101.
# Usage: ./scripts/setup-ak-openfang.sh [host]
# Default host: 10.10.1.127:4200

set -euo pipefail

HOST="${1:-10.10.1.127:4200}"
BASE="http://${HOST}"

echo "[setup-ak] Using OpenFang at $BASE"

# 1. Spawn ak agents (if not already in DB)
echo "[setup-ak] Spawning ak agents..."
for agent in ak-enrich ak-tidy ak-snapshot ak-digest; do
    curl -sf -X POST "$BASE/api/agents" \
        -H "Content-Type: application/json" \
        -d "{\"manifest_path\": \"/data/agents/${agent}/agent.toml\"}" \
        && echo "[setup-ak] Spawned $agent" \
        || echo "[setup-ak] WARN: $agent may already exist"
done

# 2. Register ak-maintenance workflow
echo "[setup-ak] Registering ak-maintenance workflow..."
WORKFLOW_RESP=$(curl -sf -X POST "$BASE/api/workflows" \
    -H "Content-Type: application/json" \
    -d @openfang/workflows/ak-maintenance.json)
WORKFLOW_ID=$(echo "$WORKFLOW_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "[setup-ak] Workflow ID: $WORKFLOW_ID"

# 3. Get ak-snapshot agent ID (for cron job ownership)
SNAPSHOT_ID=$(curl -sf "$BASE/api/agents" | python3 -c "
import sys, json
agents = json.load(sys.stdin)
for a in agents:
    if a.get('name') == 'ak-snapshot':
        print(a['id'])
        break
")
echo "[setup-ak] ak-snapshot agent ID: $SNAPSHOT_ID"

# 4. Register cron job: run ak-maintenance workflow every 6 hours
echo "[setup-ak] Registering 6-hour maintenance cron..."
curl -sf -X POST "$BASE/api/cron" \
    -H "Content-Type: application/json" \
    -d "{
        \"agent_id\": \"$SNAPSHOT_ID\",
        \"name\": \"ak-maintenance-6h\",
        \"enabled\": true,
        \"schedule\": {\"kind\": \"cron\", \"expr\": \"0 */6 * * *\"},
        \"action\": {\"kind\": \"workflow_run\", \"workflow_id\": \"$WORKFLOW_ID\"},
        \"delivery\": {\"kind\": \"none\"}
    }"
echo "[setup-ak] Cron registered."

# 5. Get ak-digest agent ID
DIGEST_ID=$(curl -sf "$BASE/api/agents" | python3 -c "
import sys, json
agents = json.load(sys.stdin)
for a in agents:
    if a.get('name') == 'ak-digest':
        print(a['id'])
        break
")
echo "[setup-ak] ak-digest agent ID: $DIGEST_ID"

# 6. Register ContentMatch trigger: fire ak-digest when workflow completes
echo "[setup-ak] Registering ak-digest ContentMatch trigger..."
curl -sf -X POST "$BASE/api/triggers" \
    -H "Content-Type: application/json" \
    -d "{
        \"agent_id\": \"$DIGEST_ID\",
        \"pattern\": {\"type\": \"content_match\", \"substring\": \"ak-maintenance complete\"},
        \"prompt_template\": \"The ak-maintenance workflow just completed. Run your cross-project digest now.\",
        \"max_fires\": 0
    }"
echo "[setup-ak] Trigger registered."

echo "[setup-ak] Done. Verify with:"
echo "  curl -s $BASE/api/workflows | python3 -m json.tool"
echo "  curl -s $BASE/api/cron | python3 -m json.tool"
echo "  curl -s $BASE/api/triggers | python3 -m json.tool"
```

- [ ] **Step 2: Make executable**

```bash
chmod +x scripts/setup-ak-openfang.sh
```

- [ ] **Step 3: Commit**

```bash
git add scripts/setup-ak-openfang.sh
git commit -m "feat: add setup script for ak-maintenance workflow, cron, and digest trigger"
```

---

## Chunk 4: Session-End Hook + Mac Mini Cleanup

### Task 10: Update session-end hook

**Files:**
- Modify: `~/.claude/settings.json`

The SessionEnd hook already runs `ak ingest`. Add a second command to trigger ak-enrich on OpenFang.

- [ ] **Step 1: Read current SessionEnd hooks**

```bash
cat ~/.claude/settings.json | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d.get('hooks',{}).get('SessionEnd',[]), indent=2))"
```

- [ ] **Step 2: Add the OpenFang trigger command**

The new command fires after `ak ingest` and POSTs directly to the ak-enrich agent on OpenFang:

```json
{
  "type": "command",
  "command": "curl -sf -X POST http://10.10.1.127:4200/api/agents/ak-enrich/message -H 'Content-Type: application/json' -d '{\"message\": \"New sessions ingested. Run enrichment on recently active projects.\"}' 2>/dev/null || true"
}
```

Edit `~/.claude/settings.json` to add this as the second command in the `SessionEnd` array, after the existing `ak ingest` command.

- [ ] **Step 3: Test the hook fires correctly**

Start a new Claude Code session and end it. Check:
```bash
# On VM101
docker compose -f docker-compose.openfang.yml logs openfang --since=5m | grep "ak-enrich"
```
Expected: log entry showing ak-enrich received a message.

---

### Task 11: Remove Mac mini launchd processes

- [ ] **Step 1: Unload the ingest daemon**

```bash
launchctl unload ~/Library/LaunchAgents/com.agent-knowledge.ingest.plist
```
Expected: no output (success).

- [ ] **Step 2: Unload the snapshot job**

```bash
launchctl unload ~/Library/LaunchAgents/com.agent-knowledge.snapshot.plist
```

- [ ] **Step 3: Verify neither is running**

```bash
launchctl list | grep agent-knowledge
```
Expected: no output.

- [ ] **Step 4: Archive the plists (don't delete yet)**

```bash
mkdir -p ~/.agent-knowledge/launchd-archive
mv ~/Library/LaunchAgents/com.agent-knowledge.ingest.plist ~/.agent-knowledge/launchd-archive/
mv ~/Library/LaunchAgents/com.agent-knowledge.snapshot.plist ~/.agent-knowledge/launchd-archive/
```

Keep them archived until the OpenFang pipeline is confirmed working in production.

---

## Chunk 5: Deploy and Verify

### Task 12: Deploy to VM101

- [ ] **Step 1: Push changes**

```bash
git push
```

- [ ] **Step 2: SSH to VM101 and pull**

```bash
ssh root@10.10.1.127
cd /opt/inframon
git pull
```

- [ ] **Step 3: Rebuild and restart**

```bash
docker compose -f docker-compose.openfang.yml up -d --build
```

- [ ] **Step 4: Verify ak binary works in container**

```bash
docker compose -f docker-compose.openfang.yml exec openfang ak --version
docker compose -f docker-compose.openfang.yml exec openfang ak stats
```
Expected: ak version output, then stats showing ~1836 memories.

- [ ] **Step 5: Verify pg-ak is reachable from container**

```bash
docker compose -f docker-compose.openfang.yml exec openfang python3 -c "
import subprocess
result = subprocess.run(['ak', 'stats'], capture_output=True, text=True)
print(result.stdout[:200])
print('STDERR:', result.stderr[:100] if result.stderr else 'none')
"
```
Expected: stats output with memory counts.

---

### Task 13: Run setup script and spawn agents

- [ ] **Step 1: From Mac mini, run the setup script against VM101**

```bash
cd ~/git/inframon
./scripts/setup-ak-openfang.sh 10.10.1.127:4200
```
Expected: all 4 agents spawned, workflow ID printed, cron registered, trigger registered.

- [ ] **Step 2: Manually spawn ak agents if needed**

If auto-spawn fails (new agents not in DB), spawn manually:
```bash
ssh root@10.10.1.127 "cd /opt/inframon && \
  docker compose -f docker-compose.openfang.yml exec openfang \
  openfang agent spawn /data/agents/ak-enrich/agent.toml && \
  openfang agent spawn /data/agents/ak-tidy/agent.toml && \
  openfang agent spawn /data/agents/ak-snapshot/agent.toml && \
  openfang agent spawn /data/agents/ak-digest/agent.toml"
```

- [ ] **Step 3: Verify agents are running**

```bash
curl -s http://10.10.1.127:4200/api/agents | python3 -c "
import sys, json
for a in json.load(sys.stdin):
    if 'ak-' in a.get('name', ''):
        print(a['name'], a['state'])
"
```
Expected: ak-enrich/ak-tidy/ak-snapshot/ak-digest all in `running` state.

- [ ] **Step 4: Verify cron and trigger registered**

```bash
curl -s http://10.10.1.127:4200/api/cron | python3 -m json.tool | grep -A3 "ak-maintenance"
curl -s http://10.10.1.127:4200/api/triggers | python3 -m json.tool | grep -A3 "ak-maintenance"
```

---

### Task 14: End-to-end smoke test

- [ ] **Step 1: Trigger ak-enrich manually**

```bash
curl -s -X POST http://10.10.1.127:4200/api/agents/ak-enrich/message \
  -H "Content-Type: application/json" \
  -d '{"message": "Test run: enrich a single small project (agent-knowledge)."}'
```

- [ ] **Step 2: Watch logs**

```bash
ssh root@10.10.1.127 "docker compose -f /opt/inframon/docker-compose.openfang.yml logs -f openfang" 2>&1 | grep -i "ak-enrich\|enrichment\|ak stats"
```
Expected: ak-enrich runs, prints enrichment summary within 2-3 minutes.

- [ ] **Step 3: Trigger the full workflow manually**

```bash
WORKFLOW_ID=$(curl -s http://10.10.1.127:4200/api/workflows | python3 -c "
import sys, json
for w in json.load(sys.stdin):
    if w['name'] == 'ak-maintenance':
        print(w['id'])
        break
")
curl -s -X POST "http://10.10.1.127:4200/api/workflows/$WORKFLOW_ID/run" \
  -H "Content-Type: application/json" \
  -d '{"input": "Full maintenance run."}'
```

- [ ] **Step 4: Verify ak-digest fires after workflow**

Watch logs for `ak-maintenance complete` output, then ak-digest activation:
```bash
ssh root@10.10.1.127 "docker compose -f /opt/inframon/docker-compose.openfang.yml logs -f openfang" 2>&1 | grep -i "digest\|maintenance complete"
```

- [ ] **Step 5: Confirm launchd is gone and not needed**

```bash
launchctl list | grep agent-knowledge
```
Expected: empty. Session-end hook + OpenFang is now the only pipeline.

---

## Notes for Future Work

- **`#ak-digest` Matrix room:** When ready, update ak-digest agent.toml to use `matrix_notify` skill to post digest to new Matrix room.
- **SSH/rsync catch-up:** Future Hand on OpenFang that rsyncs JSONL files from Mac mini nightly as a fallback for missed sessions.
- **Per-project fan-out:** Once the sequential workflow is stable, convert dedup/tidy/enrich steps to fan-out per project for parallelism.
- **A2A upgrade:** If Mac mini needs structured task tracking (vs fire-and-forget), switch the session-end hook to A2A task submission.
