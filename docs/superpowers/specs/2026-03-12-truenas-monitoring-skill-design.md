# TrueNAS Monitoring Skill Design

## Goal

Build an OpenFang skill for monitoring TrueNAS SCALE via WebSocket JSON-RPC 2.0, using the official `truenas-api-client` package managed by `uv`. Read-only monitoring scope only.

## Architecture

Python package with `pyproject.toml` for dependency management via `uv`. Uses `truenas-api-client` (official iXsystems library) for WebSocket JSON-RPC 2.0. Single CLI script with argparse subcommands, JSON output — same pattern as existing skills but with proper dependency management.

**Connection**: WebSocket at `wss://<host>:6000/api/current`, authenticated via API key.

## Target

- TrueNAS TS140 at 10.10.1.140
- TrueNAS SCALE 25.04.2.6
- Pool: `tank` (mirror)
- Services: cifs, nfs, ssh, ups, smartd
- Replication: `share-zfs-truenas`

## Skill Structure

```
skills/truenas-monitoring/
├── SKILL.md              # Metadata, trigger words, usage docs, investigation patterns
├── pyproject.toml         # uv-managed deps (truenas-api-client)
├── uv.lock               # Locked dependencies
└── scripts/
    └── truenas_query.py   # argparse CLI, JSON output
```

## Commands

| Command | API Method | Purpose |
|---------|-----------|---------|
| `system-info` | `system.info` | Version, hostname, uptime, CPU, memory |
| `pools` | `pool.query` | Pool health, status, topology, scrub state |
| `alerts` | `alert.list` | Active alerts with severity and formatted text |
| `services` | `service.query` | Running/stopped services with enable state |
| `datasets` | `pool.dataset.query` | Dataset list with space usage |
| `snapshots` | `zfs.snapshot.query` | Snapshots, optionally filtered by dataset |
| `replication` | `replication.query` | Replication task status |
| `disks` | `disk.query` | Physical disks with SMART status |

## CLI Interface

```bash
# Run via uv from the skill directory
uv run --directory /data/skills/truenas-monitoring python scripts/truenas_query.py <command> [options]

# Examples
uv run ... python scripts/truenas_query.py pools
uv run ... python scripts/truenas_query.py alerts
uv run ... python scripts/truenas_query.py snapshots --dataset tank/share
uv run ... python scripts/truenas_query.py system-info
```

## Environment Variables

| Var | Purpose | Example |
|-----|---------|---------|
| `TRUENAS_URL` | TrueNAS host URL | `https://10.10.1.140` |
| `TRUENAS_API_KEY` | API key for WebSocket auth | (64-char key) |

Recovered from `/proc/1/environ` per OpenFang pattern.

## API Response Shapes (validated)

### pool.query
```json
[{"id": 1, "name": "tank", "status": "ONLINE", "healthy": true,
  "scan": {"function": "SCRUB", "state": "FINISHED", "errors": 0},
  "topology": {"data": [{"name": "mirror-0", "type": "MIRROR", "status": "ONLINE"}]}}]
```

### alert.list
```json
[{"level": "CRITICAL", "klass": "SMART", "formatted": "Device: /dev/sdc ...",
  "dismissed": false, "last_occurrence": {"$date": 1772949529000}}]
```

### service.query
```json
[{"service": "cifs", "state": "RUNNING", "enable": true}]
```

### system.info
```json
{"version": "25.04.2.6", "hostname": "truenas-ts140",
 "uptime_seconds": 259746, "model": "Intel Xeon E3-1225 v3", "cores": 4}
```

### replication.query
```json
[{"name": "share-zfs-truenas", "state": {"state": "FINISHED"}}]
```

## Container Changes

### Dockerfile.openfang
Add uv installation:
```dockerfile
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"
```

### docker-compose.openfang.yml
Add env vars:
```yaml
- TRUENAS_URL=${TRUENAS_URL}
- TRUENAS_API_KEY=${TRUENAS_API_KEY}
```

### .env
```
TRUENAS_URL=https://10.10.1.140
TRUENAS_API_KEY=<created via TrueNAS UI or midclt>
```

## API Key Creation

Create a read-only API key on TrueNAS:
```bash
ssh root@truenas-scale midclt call api_key.create '{"name": "inframon-monitoring"}'
```
The key is returned once — copy it immediately.

## Scope Boundaries

**In scope**: Read-only monitoring queries (pools, alerts, services, datasets, snapshots, replication, disks, system info)

**Out of scope**: Write operations, app management, Dockge, media services, dataset creation/deletion

## Investigation Patterns

- **"Check NAS health"** → `pools` + `alerts` + `services`
- **"Any disk issues?"** → `disks` + `alerts` (filter klass=SMART)
- **"Snapshot status"** → `snapshots` + `replication`
- **"What's running?"** → `services` + `system-info`
- **"Storage capacity"** → `datasets`

## Future: uv-managed skill pattern

This skill establishes the pattern for skills with dependencies:
1. `pyproject.toml` in skill directory with deps declared
2. `uv run --directory /data/skills/<skill>` to execute with correct venv
3. uv installed in container, handles venv creation + dep resolution
4. Existing stdlib-only skills continue working unchanged
