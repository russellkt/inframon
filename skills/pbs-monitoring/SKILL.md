---
name: pbs-monitoring
description: Monitor Proxmox Backup Server instances — check datastore usage, backup status, verify/sync jobs, garbage collection, and find VMs missing recent backups. Use when asked about backups, backup status, PBS storage, missing backups, verify jobs, sync jobs, or anything related to Proxmox Backup Server.
---

# PBS Monitoring

Query three PBS instances (primary, ts140, offsite) via `scripts/pbs_query.py`.

## PBS Instances

| Name | IP | Host | Storage |
|------|-----|------|---------|
| primary | 10.10.1.141 | pve-r720 (CT 851) | ZFS `spinners` ~3.4TB |
| ts140 | 10.10.1.145 | truenas-ts140 (Incus LXC) | ZFS `tank` ~3.8TB |
| offsite | 100.100.58.6 | pve-705mini (CT 821) | ZFS mirror 2x6TB ~1.4TB |

## Commands

Run via `python3 /path/to/scripts/pbs_query.py <command> [options]`.

All commands accept `--instance NAME` to query one instance (default: all).

```
datastores                          # Storage pools with usage and dedup ratio
snapshots [--datastore X] [--vmid N] # Backup snapshots, filter by store or VMID
backup-jobs                         # Recent backup task history
verify-jobs                         # Verification job config + last run
sync-jobs                           # Sync job config + last run (offsite replication)
gc-status [--datastore X]           # Garbage collection status per datastore
tasks [--typefilter TYPE] [--limit N] # Recent tasks (backup, verify, syncjob, prune, garbage_collection)
task-log --instance NAME --upid UPID # Detailed log for a specific task
missing-backups [--days N]          # VMs in PVE without recent PBS backups (default: 3 days)
```

## Investigation Patterns

**"Are backups running?"** -> `backup-jobs` to see recent backup tasks, check for failures.

**"Is datastore getting full?"** -> `datastores` to check usage percentages and dedup ratios.

**"Which VMs aren't backed up?"** -> `missing-backups` cross-references PVE VM list against PBS snapshots. This is the most valuable check.

**"Is offsite sync working?"** -> `sync-jobs --instance offsite` to check replication status.

**"Did verification pass?"** -> `verify-jobs` to see verify job results and any failed checks.

**Task failure details** -> Find the UPID from `tasks`, then `task-log --instance NAME --upid UPID`.

## Environment Variables

Configured in docker-compose:
- `PBS_INSTANCES` — `primary:10.10.1.141,ts140:10.10.1.145,offsite:100.100.58.6`
- `PBS_API_TOKEN_ID` — shared token (e.g. `inframon@pbs!monitoring`)
- `PBS_API_TOKEN_SECRET` — shared token secret
- Per-instance overrides: `PBS_PRIMARY_TOKEN_ID`, `PBS_OFFSITE_TOKEN_ID`, etc.

## Dependencies

Requires `requests` and `urllib3` (both in standard Python environments).
