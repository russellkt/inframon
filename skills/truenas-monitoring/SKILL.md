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
| truenas-ts140 | 10.10.1.78 | Xeon E3-1225 v3, 4c | tank (mirror) |

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
