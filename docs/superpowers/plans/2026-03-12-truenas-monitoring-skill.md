# TrueNAS Monitoring Skill Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a TrueNAS SCALE monitoring skill using the official `truenas-api-client` over WebSocket JSON-RPC 2.0, with uv-managed dependencies.

**Architecture:** Python CLI script using `truenas-api-client` for WebSocket communication. uv manages the venv and deps via `pyproject.toml`. The script connects, runs a query, prints JSON, disconnects. Follows existing skill pattern (SKILL.md + scripts/).

**Tech Stack:** Python 3.11, truenas-api-client (official iXsystems), uv package manager

**Spec:** `docs/superpowers/specs/2026-03-12-truenas-monitoring-skill-design.md`

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `skills/truenas-monitoring/SKILL.md` | Create | Skill metadata, trigger words, usage docs |
| `skills/truenas-monitoring/pyproject.toml` | Create | uv project with truenas-api-client dep |
| `skills/truenas-monitoring/scripts/truenas_query.py` | Create | CLI tool — argparse, 8 subcommands, JSON output |
| `Dockerfile.openfang` | Modify | Add uv installation |
| `docker-compose.openfang.yml` | Modify | Add TRUENAS_URL, TRUENAS_API_KEY env vars |
| `.env` | Modify | Add TrueNAS credentials |
| `openfang/agents/inframon/agent.toml` | Modify | Add truenas-monitoring capabilities |
| `CLAUDE.md` | Modify | Add TrueNAS to infrastructure section |

---

## Chunk 1: Container Setup & API Key

### Task 1: Add uv to Dockerfile

**Files:**
- Modify: `Dockerfile.openfang`

- [ ] **Step 1: Add uv installation after apt-get**

  In `Dockerfile.openfang`, after the `apt-get` block and before the OpenFang install, add:
  ```dockerfile
  # Install uv for Python package management (skills with dependencies)
  RUN curl -LsSf https://astral.sh/uv/install.sh | sh
  ENV PATH="/root/.local/bin:${PATH}"
  ```

- [ ] **Step 2: Verify Dockerfile builds**

  ```bash
  docker compose -f docker-compose.openfang.yml build 2>&1 | tail -5
  ```
  Expected: Build succeeds.

- [ ] **Step 3: Verify uv works in container**

  ```bash
  docker compose -f docker-compose.openfang.yml up -d
  docker exec bmic-inframon-openfang uv --version
  ```
  Expected: Prints uv version (e.g. `uv 0.7.x`).

- [ ] **Step 4: Commit**

  ```bash
  git add Dockerfile.openfang
  git commit -m "feat: add uv to OpenFang container for skill dependency management"
  ```

### Task 2: Create TrueNAS API Key

**Files:** None (external setup)

- [ ] **Step 1: Create API key on TrueNAS**

  ```bash
  ssh root@truenas-scale "midclt call api_key.create '{\"name\": \"inframon-monitoring\"}'"
  ```
  Copy the key from the output — it's shown once only.

- [ ] **Step 2: Add TrueNAS env vars to .env**

  Add to `.env`:
  ```
  # ── TrueNAS SCALE ─────────────────────────────────────────────────
  TRUENAS_URL=https://10.10.1.140
  TRUENAS_API_KEY=<paste key from step 1>
  ```

- [ ] **Step 3: Add env vars to docker-compose.openfang.yml**

  In the `environment` section, add:
  ```yaml
      - TRUENAS_URL=${TRUENAS_URL}
      - TRUENAS_API_KEY=${TRUENAS_API_KEY}
  ```

- [ ] **Step 4: Commit docker-compose change**

  ```bash
  git add docker-compose.openfang.yml
  git commit -m "feat: pass TrueNAS env vars through docker-compose"
  ```

---

## Chunk 2: Skill Scaffold & Dependencies

### Task 3: Create pyproject.toml

**Files:**
- Create: `skills/truenas-monitoring/pyproject.toml`

- [ ] **Step 1: Create skill directory**

  ```bash
  mkdir -p skills/truenas-monitoring/scripts
  ```

- [ ] **Step 2: Create pyproject.toml**

  Create `skills/truenas-monitoring/pyproject.toml`:
  ```toml
  [project]
  name = "truenas-monitoring"
  version = "0.1.0"
  description = "TrueNAS SCALE monitoring skill for OpenFang"
  requires-python = ">=3.11"
  dependencies = [
      "truenas-api-client @ git+https://github.com/truenas/api_client.git@TS-25.04.2",
  ]
  ```

- [ ] **Step 3: Run uv sync inside container to verify deps install**

  ```bash
  docker compose -f docker-compose.openfang.yml up -d --build
  docker exec bmic-inframon-openfang uv sync --directory /data/skills/truenas-monitoring
  ```
  Expected: Dependencies resolve and install. If this fails with the git dep, fall back to:
  ```toml
  dependencies = ["websocket-client"]
  ```
  and implement the WebSocket JSON-RPC client manually (~50 lines).

- [ ] **Step 4: Verify import works**

  ```bash
  docker exec bmic-inframon-openfang uv run --directory /data/skills/truenas-monitoring \
    python3 -c "from truenas_api_client import Client; print('OK')"
  ```
  Expected: `OK`

  If `truenas-api-client` doesn't work well, the fallback is:
  ```bash
  docker exec bmic-inframon-openfang uv run --directory /data/skills/truenas-monitoring \
    python3 -c "import websocket; print('OK')"
  ```

- [ ] **Step 5: Commit**

  ```bash
  git add skills/truenas-monitoring/pyproject.toml
  git commit -m "feat: add truenas-monitoring skill with uv-managed deps"
  ```

---

## Chunk 3: CLI Script Implementation

### Task 4: Write truenas_query.py

**Files:**
- Create: `skills/truenas-monitoring/scripts/truenas_query.py`

- [ ] **Step 1: Create the CLI script**

  Create `skills/truenas-monitoring/scripts/truenas_query.py`:

  ```python
  #!/usr/bin/env python3
  """TrueNAS SCALE monitoring tool for inframon.

  Queries TrueNAS via WebSocket JSON-RPC 2.0 using truenas-api-client.

  Environment variables:
    TRUENAS_URL       — TrueNAS host URL (e.g. https://10.10.1.140)
    TRUENAS_API_KEY   — API key for authentication

  Usage:
    truenas_query.py system-info
    truenas_query.py pools
    truenas_query.py alerts [--level LEVEL]
    truenas_query.py services [--running-only]
    truenas_query.py datasets [--pool NAME]
    truenas_query.py snapshots [--dataset NAME]
    truenas_query.py replication
    truenas_query.py disks
  """

  import argparse
  import json
  import os
  import sys
  from pathlib import Path

  # OpenFang strips env vars from subprocesses — recover from init process
  _proc_env = Path("/proc/1/environ")
  if _proc_env.exists():
      for entry in _proc_env.read_bytes().split(b"\0"):
          if b"=" in entry:
              k, v = entry.decode("utf-8", errors="replace").split("=", 1)
              os.environ.setdefault(k, v)

  from truenas_api_client import Client


  def get_client():
      """Create a TrueNAS WebSocket client."""
      url = os.environ.get("TRUENAS_URL")
      api_key = os.environ.get("TRUENAS_API_KEY")

      if not url:
          print(json.dumps({"error": "TRUENAS_URL not set"}))
          sys.exit(1)
      if not api_key:
          print(json.dumps({"error": "TRUENAS_API_KEY not set"}))
          sys.exit(1)

      # Convert https:// to wss:// for WebSocket
      ws_url = url.replace("https://", "wss://").replace("http://", "ws://")
      # TrueNAS 25.04 WebSocket endpoint
      ws_url = f"{ws_url}:6000/api/current"

      return Client(ws_url, api_key=api_key, verify_ssl=False)


  def cmd_system_info(args):
      with get_client() as c:
          info = c.call("system.info")
          print(json.dumps({
              "version": info.get("version"),
              "hostname": info.get("hostname"),
              "uptime_seconds": info.get("uptime_seconds"),
              "model": info.get("model"),
              "cores": info.get("cores"),
              "physical_mem": info.get("physical_mem"),
          }, indent=2))


  def cmd_pools(args):
      with get_client() as c:
          pools = c.call("pool.query")
          result = []
          for p in pools:
              scan = p.get("scan", {})
              result.append({
                  "name": p.get("name"),
                  "status": p.get("status"),
                  "healthy": p.get("healthy"),
                  "scan_state": scan.get("state"),
                  "scan_errors": scan.get("errors"),
                  "topology": [
                      {"name": v.get("name"), "type": v.get("type"), "status": v.get("status")}
                      for v in p.get("topology", {}).get("data", [])
                  ],
              })
          print(json.dumps(result, indent=2))


  def cmd_alerts(args):
      with get_client() as c:
          alerts = c.call("alert.list")
          result = []
          for a in alerts:
              if args.level and a.get("level") != args.level.upper():
                  continue
              result.append({
                  "level": a.get("level"),
                  "klass": a.get("klass"),
                  "formatted": a.get("formatted"),
                  "dismissed": a.get("dismissed"),
              })
          print(json.dumps(result, indent=2))


  def cmd_services(args):
      with get_client() as c:
          services = c.call("service.query")
          result = []
          for s in services:
              if args.running_only and s.get("state") != "RUNNING":
                  continue
              result.append({
                  "service": s.get("service"),
                  "state": s.get("state"),
                  "enable": s.get("enable"),
              })
          print(json.dumps(result, indent=2))


  def cmd_datasets(args):
      with get_client() as c:
          datasets = c.call("pool.dataset.query")
          result = []
          for d in datasets:
              if args.pool and not d.get("name", "").startswith(args.pool):
                  continue
              used = d.get("used", {})
              avail = d.get("available", {})
              result.append({
                  "name": d.get("name"),
                  "type": d.get("type"),
                  "used": used.get("parsed") if isinstance(used, dict) else used,
                  "available": avail.get("parsed") if isinstance(avail, dict) else avail,
              })
          print(json.dumps(result, indent=2))


  def cmd_snapshots(args):
      with get_client() as c:
          snapshots = c.call("zfs.snapshot.query")
          result = []
          for s in snapshots:
              sname = s.get("name", "")
              if args.dataset and not sname.startswith(args.dataset + "@"):
                  continue
              result.append({
                  "name": sname,
                  "dataset": s.get("dataset"),
                  "created": s.get("properties", {}).get("creation", {}).get("value"),
                  "used": s.get("properties", {}).get("used", {}).get("value"),
                  "referenced": s.get("properties", {}).get("referenced", {}).get("value"),
              })
          print(json.dumps(result, indent=2))


  def cmd_replication(args):
      with get_client() as c:
          reps = c.call("replication.query")
          result = []
          for r in reps:
              state = r.get("state", {})
              result.append({
                  "name": r.get("name"),
                  "state": state.get("state"),
                  "last_snapshot": state.get("last_snapshot"),
              })
          print(json.dumps(result, indent=2))


  def cmd_disks(args):
      with get_client() as c:
          disks = c.call("disk.query")
          result = []
          for d in disks:
              result.append({
                  "name": d.get("name"),
                  "serial": d.get("serial"),
                  "size": d.get("size"),
                  "model": d.get("model"),
                  "type": d.get("type"),
              })
          print(json.dumps(result, indent=2))


  def main():
      parser = argparse.ArgumentParser(description="TrueNAS SCALE monitoring tool")
      sub = parser.add_subparsers(dest="command", required=True)

      sub.add_parser("system-info", help="System version, hostname, uptime")

      sub.add_parser("pools", help="Pool health and topology")

      p_alerts = sub.add_parser("alerts", help="Active alerts")
      p_alerts.add_argument("--level", help="Filter by level (CRITICAL, WARNING, INFO)")

      p_svc = sub.add_parser("services", help="System services")
      p_svc.add_argument("--running-only", action="store_true", help="Only show running")

      p_ds = sub.add_parser("datasets", help="ZFS datasets with usage")
      p_ds.add_argument("--pool", help="Filter by pool name prefix")

      p_snap = sub.add_parser("snapshots", help="ZFS snapshots")
      p_snap.add_argument("--dataset", help="Filter by dataset name")

      sub.add_parser("replication", help="Replication task status")

      sub.add_parser("disks", help="Physical disk info")

      args = parser.parse_args()

      commands = {
          "system-info": cmd_system_info,
          "pools": cmd_pools,
          "alerts": cmd_alerts,
          "services": cmd_services,
          "datasets": cmd_datasets,
          "snapshots": cmd_snapshots,
          "replication": cmd_replication,
          "disks": cmd_disks,
      }

      commands[args.command](args)


  if __name__ == "__main__":
      main()
  ```

  **Note:** If `truenas-api-client` doesn't work as expected (different constructor args, auth method), adapt `get_client()` accordingly. The client's actual API may differ — check the source at `https://github.com/truenas/api_client`. The fallback is to use `websocket-client` directly and implement the JSON-RPC handshake (~50 lines).

- [ ] **Step 2: Test each command from the container**

  ```bash
  docker compose -f docker-compose.openfang.yml up -d --build

  # Sync deps first
  docker exec bmic-inframon-openfang uv sync --directory /data/skills/truenas-monitoring

  # Test each command
  docker exec bmic-inframon-openfang uv run --directory /data/skills/truenas-monitoring \
    python3 scripts/truenas_query.py system-info

  docker exec bmic-inframon-openfang uv run --directory /data/skills/truenas-monitoring \
    python3 scripts/truenas_query.py pools

  docker exec bmic-inframon-openfang uv run --directory /data/skills/truenas-monitoring \
    python3 scripts/truenas_query.py alerts

  docker exec bmic-inframon-openfang uv run --directory /data/skills/truenas-monitoring \
    python3 scripts/truenas_query.py services --running-only

  docker exec bmic-inframon-openfang uv run --directory /data/skills/truenas-monitoring \
    python3 scripts/truenas_query.py datasets --pool tank

  docker exec bmic-inframon-openfang uv run --directory /data/skills/truenas-monitoring \
    python3 scripts/truenas_query.py snapshots --dataset tank/share

  docker exec bmic-inframon-openfang uv run --directory /data/skills/truenas-monitoring \
    python3 scripts/truenas_query.py replication

  docker exec bmic-inframon-openfang uv run --directory /data/skills/truenas-monitoring \
    python3 scripts/truenas_query.py disks
  ```
  Expected: Each command prints valid JSON.

- [ ] **Step 3: Commit**

  ```bash
  git add skills/truenas-monitoring/scripts/truenas_query.py
  git commit -m "feat: implement truenas_query.py CLI with 8 monitoring commands"
  ```

---

## Chunk 4: Skill Metadata & Agent Integration

### Task 5: Create SKILL.md

**Files:**
- Create: `skills/truenas-monitoring/SKILL.md`

- [ ] **Step 1: Create SKILL.md**

  Create `skills/truenas-monitoring/SKILL.md`:
  ```markdown
  ---
  name: truenas-monitoring
  description: Monitor TrueNAS SCALE — check pool health, alerts, services, datasets, snapshots, replication, and disk status. Use when asked about NAS, storage, TrueNAS, ZFS, snapshots, replication, or disk health.
  trigger_words:
    - truenas
    - nas
    - zfs
    - storage pool
    - snapshot
    - replication
    - disk health
    - scrub
  ---

  # TrueNAS SCALE Monitoring

  Query TrueNAS SCALE 25.04 via WebSocket JSON-RPC 2.0 using `truenas_query.py`.

  ## Target

  | Host | IP | Hardware | Pool |
  |------|-----|----------|------|
  | truenas-ts140 | 10.10.1.140 | Xeon E3-1225 v3, 4c | tank (mirror) |

  ## Commands

  Run via `uv run --directory /data/skills/truenas-monitoring python3 scripts/truenas_query.py <command> [options]`.

  ```
  system-info                         # Version, hostname, uptime, CPU
  pools                               # Pool health, topology, scrub state
  alerts [--level LEVEL]              # Active alerts (CRITICAL, WARNING, INFO)
  services [--running-only]           # Services with state and enable flag
  datasets [--pool NAME]              # ZFS datasets with space usage
  snapshots [--dataset NAME]          # ZFS snapshots, optionally filtered
  replication                         # Replication task status
  disks                               # Physical disk info
  ```

  ## Investigation Patterns

  **"Check NAS health"** → `pools` + `alerts` + `services`

  **"Any disk issues?"** → `disks` + `alerts --level CRITICAL`

  **"Snapshot status"** → `snapshots` + `replication`

  **"Storage capacity"** → `datasets --pool tank`

  **"What's running on the NAS?"** → `services --running-only` + `system-info`

  ## Environment Variables

  Configured in docker-compose:
  - `TRUENAS_URL` — TrueNAS host URL (e.g. https://10.10.1.140)
  - `TRUENAS_API_KEY` — API key for WebSocket auth

  ## Dependencies

  Managed by uv via `pyproject.toml`:
  - `truenas-api-client` — Official iXsystems WebSocket JSON-RPC client
  ```

- [ ] **Step 2: Verify skill loads in OpenFang**

  ```bash
  docker compose -f docker-compose.openfang.yml restart
  sleep 3
  docker compose -f docker-compose.openfang.yml logs --tail=10 | grep -i truenas
  ```
  Expected: `Loaded skill: truenas-monitoring`

- [ ] **Step 3: Commit**

  ```bash
  git add skills/truenas-monitoring/SKILL.md
  git commit -m "docs: add truenas-monitoring SKILL.md with trigger words and usage"
  ```

### Task 6: Update Agent Config

**Files:**
- Modify: `openfang/agents/inframon/agent.toml`

- [ ] **Step 1: Add uv run pattern to shell capabilities**

  In `agent.toml` `[capabilities]` section, add to the `shell` list:
  ```toml
  "uv run --directory /data/skills/* python3 *",
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add openfang/agents/inframon/agent.toml
  git commit -m "feat: allow uv run in agent shell capabilities for skill deps"
  ```

### Task 7: Update Documentation

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add TrueNAS to Infrastructure section**

  In `CLAUDE.md`, after the Switches section, add:
  ```markdown
  ### TrueNAS
  truenas-ts140 (10.10.1.140) — TrueNAS SCALE 25.04, pool: tank (mirror)
  ```

- [ ] **Step 2: Add TRUENAS env vars to Environment Variables section**

  Add:
  ```markdown
  - `TRUENAS_URL`, `TRUENAS_API_KEY` — TrueNAS SCALE monitoring
  ```

- [ ] **Step 3: Commit**

  ```bash
  git add CLAUDE.md
  git commit -m "docs: add TrueNAS to infrastructure inventory and env vars"
  ```

---

## Chunk 5: Final Validation & Cleanup

### Task 8: End-to-End Test

**Files:** None (runtime validation)

- [ ] **Step 1: Full rebuild and deploy**

  ```bash
  docker compose -f docker-compose.openfang.yml up -d --build
  ```

- [ ] **Step 2: Run all commands and verify JSON output**

  ```bash
  for cmd in system-info pools alerts services datasets snapshots replication disks; do
    echo "=== $cmd ==="
    docker exec bmic-inframon-openfang uv run --directory /data/skills/truenas-monitoring \
      python3 scripts/truenas_query.py $cmd 2>&1 | head -10
    echo
  done
  ```
  Expected: Each prints valid JSON, no errors.

- [ ] **Step 3: Test from Matrix**

  Send a message in the Matrix room:
  ```
  check truenas health
  ```
  Expected: The agent uses the truenas-monitoring skill to query pools, alerts, services.

- [ ] **Step 4: Close the bead**

  ```bash
  bd close im-pt1 --reason="TrueNAS monitoring skill implemented with 8 commands via WebSocket JSON-RPC 2.0, uv-managed deps"
  ```

- [ ] **Step 5: Record memory**

  ```bash
  bd remember "truenas-monitoring-skill: TrueNAS SCALE 25.04 monitoring skill at skills/truenas-monitoring/. Uses truenas-api-client via WebSocket JSON-RPC 2.0 (wss://host:6000/api/current). 8 commands: system-info, pools, alerts, services, datasets, snapshots, replication, disks. uv-managed deps (pyproject.toml). Env: TRUENAS_URL, TRUENAS_API_KEY. Target: truenas-ts140 (10.10.1.140). First skill using uv for dependency management."
  ```

- [ ] **Step 6: Push**

  ```bash
  git push origin main
  ```

---

## Summary of Changes

| File | Change |
|------|--------|
| `Dockerfile.openfang` | Add uv installation |
| `docker-compose.openfang.yml` | Add TRUENAS_URL, TRUENAS_API_KEY env vars |
| `.env` | Add TrueNAS credentials |
| `skills/truenas-monitoring/pyproject.toml` | uv project with truenas-api-client dep |
| `skills/truenas-monitoring/SKILL.md` | Skill metadata and usage docs |
| `skills/truenas-monitoring/scripts/truenas_query.py` | CLI with 8 monitoring commands |
| `openfang/agents/inframon/agent.toml` | Add uv run to shell capabilities |
| `CLAUDE.md` | Add TrueNAS to infra inventory |

## Fallback Plan

If `truenas-api-client` doesn't install or work properly via uv:
1. Try `pip install` into a venv instead
2. If the client API is incompatible, use `websocket-client` package directly with manual JSON-RPC 2.0 handshake (~50 lines)
3. If WebSocket is problematic, use SSH + midclt as the transport (container already has SSH keys)
