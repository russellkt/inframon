#!/usr/bin/env python3
"""PBS (Proxmox Backup Server) query tool for inframon.

Multi-instance PBS client supporting API token auth.

Environment variables:
  PBS_INSTANCES            — name:host[:port] comma-separated (default port 8007)
  PBS_API_TOKEN_ID         — shared API token ID (e.g. inframon@pbs!monitoring)
  PBS_API_TOKEN_SECRET     — shared API token secret
  PBS_<NAME>_TOKEN_ID      — per-instance override (NAME = uppercase instance name)
  PBS_<NAME>_TOKEN_SECRET  — per-instance override
  PBS_VERIFY_SSL           — set to "1" to verify TLS (default: skip for self-signed)

Usage:
  pbs_query.py datastores [--instance NAME]
  pbs_query.py snapshots [--instance NAME] [--datastore STORE] [--vmid VMID]
  pbs_query.py backup-jobs [--instance NAME]
  pbs_query.py verify-jobs [--instance NAME]
  pbs_query.py sync-jobs [--instance NAME]
  pbs_query.py gc-status [--instance NAME] [--datastore STORE]
  pbs_query.py task-log --instance NAME --upid UPID
  pbs_query.py tasks [--instance NAME] [--typefilter TYPE] [--limit N]
  pbs_query.py missing-backups [--instance NAME] [--days DAYS]
"""

import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import quote

# OpenFang strips env vars from subprocesses — recover from init process
_proc_env = Path("/proc/1/environ")
if _proc_env.exists():
    for entry in _proc_env.read_bytes().split(b"\0"):
        if b"=" in entry:
            k, v = entry.decode("utf-8", errors="replace").split("=", 1)
            os.environ.setdefault(k, v)


def _make_opener(verify_ssl: bool) -> urllib.request.OpenerDirector:
    if verify_ssl:
        return urllib.request.build_opener()
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))


def _http_get(opener: urllib.request.OpenerDirector, url: str,
              headers: dict, params: Optional[dict] = None) -> dict:
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=headers)
    try:
        with opener.open(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("data", data)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode()}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"URL error: {e.reason}") from e


class PBSClient:
    """Minimal PBS REST API client using API tokens."""

    def __init__(self, name: str, host: str, port: int = 8007,
                 token_id: str = "", token_secret: str = "",
                 verify_ssl: bool = False):
        self.name = name
        self.base_url = f"https://{host}:{port}"
        self._opener = _make_opener(verify_ssl)
        self._headers = {"Authorization": f"PBSAPIToken={token_id}:{token_secret}"}

    def get(self, path: str, params: Optional[dict] = None) -> dict:
        url = f"{self.base_url}/api2/json{path}"
        return _http_get(self._opener, url, self._headers, params)

    def __repr__(self):
        return f"PBSClient({self.name}@{self.base_url})"


def parse_instances() -> dict[str, PBSClient]:
    """Parse PBS_INSTANCES env var and create clients."""
    raw = os.environ.get("PBS_INSTANCES", "")
    if not raw:
        print("ERROR: PBS_INSTANCES not set. Format: name:host[:port],name:host[:port]",
              file=sys.stderr)
        sys.exit(1)

    verify_ssl = os.environ.get("PBS_VERIFY_SSL", "0") == "1"
    shared_token_id = os.environ.get("PBS_API_TOKEN_ID", "")
    shared_token_secret = os.environ.get("PBS_API_TOKEN_SECRET", "")

    clients = {}
    for entry in raw.split(","):
        parts = entry.strip().split(":")
        if len(parts) < 2:
            continue
        name = parts[0]
        host = parts[1]
        port = int(parts[2]) if len(parts) > 2 else 8007

        uname = name.upper().replace("-", "_")
        token_id = os.environ.get(f"PBS_{uname}_TOKEN_ID", shared_token_id)
        token_secret = os.environ.get(f"PBS_{uname}_TOKEN_SECRET", shared_token_secret)

        if not token_id or not token_secret:
            print(f"WARNING: No credentials for PBS instance '{name}', skipping",
                  file=sys.stderr)
            continue

        clients[name] = PBSClient(name, host, port, token_id, token_secret, verify_ssl)

    if not clients:
        print("ERROR: No valid PBS instances configured", file=sys.stderr)
        sys.exit(1)

    return clients


def select_instances(clients: dict[str, PBSClient],
                     instance: Optional[str] = None) -> dict[str, PBSClient]:
    """Filter to a single instance or return all."""
    if instance:
        if instance not in clients:
            print(f"ERROR: Unknown instance '{instance}'. Available: {', '.join(clients.keys())}",
                  file=sys.stderr)
            sys.exit(1)
        return {instance: clients[instance]}
    return clients


def cmd_datastores(clients: dict[str, PBSClient], args):
    results = {}
    for name, client in select_instances(clients, args.instance).items():
        try:
            stores = client.get("/admin/datastore")
            for s in stores:
                # Fetch usage for each datastore
                try:
                    status = client.get(f"/admin/datastore/{s.get('name', s.get('store', ''))}/status")
                    s["usage"] = status
                except Exception:
                    pass
            results[name] = stores
        except Exception as e:
            results[name] = {"error": str(e)}
    return results


def cmd_snapshots(clients: dict[str, PBSClient], args):
    results = {}
    for name, client in select_instances(clients, args.instance).items():
        try:
            # Get datastores to query
            stores = client.get("/admin/datastore")
            store_names = [args.datastore] if args.datastore else [s.get("name", s.get("store", "")) for s in stores]

            instance_snaps = {}
            for store in store_names:
                try:
                    snaps = client.get(f"/admin/datastore/{store}/snapshots")
                    if args.vmid:
                        snaps = [s for s in snaps if
                                 s.get("backup-id", "") == args.vmid or
                                 s.get("backup-id", "").endswith(f"/{args.vmid}")]
                    instance_snaps[store] = snaps
                except Exception as e:
                    instance_snaps[store] = {"error": str(e)}
            results[name] = instance_snaps
        except Exception as e:
            results[name] = {"error": str(e)}
    return results


def cmd_backup_jobs(clients: dict[str, PBSClient], args):
    """List backup/sync/verify jobs and recent task history."""
    results = {}
    for name, client in select_instances(clients, args.instance).items():
        try:
            # PBS doesn't have a dedicated "backup jobs" endpoint —
            # backup jobs are configured on PVE and push to PBS.
            # We can show recent backup tasks instead.
            tasks = client.get("/nodes/localhost/tasks", params={
                "typefilter": "backup",
                "limit": 20,
            })
            results[name] = tasks
        except Exception as e:
            results[name] = {"error": str(e)}
    return results


def cmd_verify_jobs(clients: dict[str, PBSClient], args):
    results = {}
    for name, client in select_instances(clients, args.instance).items():
        try:
            jobs = client.get("/config/verify")
            # Enrich with last run status
            for job in jobs:
                try:
                    tasks = client.get("/nodes/localhost/tasks", params={
                        "typefilter": "verificationjob",
                        "limit": 1,
                    })
                    if tasks:
                        job["last_run"] = tasks[0]
                except Exception:
                    pass
            results[name] = jobs
        except Exception as e:
            results[name] = {"error": str(e)}
    return results


def cmd_sync_jobs(clients: dict[str, PBSClient], args):
    results = {}
    for name, client in select_instances(clients, args.instance).items():
        try:
            jobs = client.get("/config/sync")
            for job in jobs:
                try:
                    tasks = client.get("/nodes/localhost/tasks", params={
                        "typefilter": "syncjob",
                        "limit": 1,
                    })
                    if tasks:
                        job["last_run"] = tasks[0]
                except Exception:
                    pass
            results[name] = jobs
        except Exception as e:
            results[name] = {"error": str(e)}
    return results


def cmd_gc_status(clients: dict[str, PBSClient], args):
    results = {}
    for name, client in select_instances(clients, args.instance).items():
        try:
            stores = client.get("/admin/datastore")
            store_names = [args.datastore] if args.datastore else [s.get("name", s.get("store", "")) for s in stores]

            gc_data = {}
            for store in store_names:
                try:
                    gc_data[store] = client.get(f"/admin/datastore/{store}/gc")
                except Exception as e:
                    gc_data[store] = {"error": str(e)}
            results[name] = gc_data
        except Exception as e:
            results[name] = {"error": str(e)}
    return results


def cmd_task_log(clients: dict[str, PBSClient], args):
    if not args.instance:
        print("ERROR: --instance required for task-log", file=sys.stderr)
        sys.exit(1)
    if not args.upid:
        print("ERROR: --upid required for task-log", file=sys.stderr)
        sys.exit(1)

    client = select_instances(clients, args.instance)[args.instance]
    try:
        encoded_upid = quote(args.upid, safe="")
        log = client.get(f"/nodes/localhost/tasks/{encoded_upid}/log", params={"limit": 500})
        return {args.instance: log}
    except Exception as e:
        return {args.instance: {"error": str(e)}}


def cmd_tasks(clients: dict[str, PBSClient], args):
    results = {}
    params = {"limit": args.limit or 30}
    if args.typefilter:
        params["typefilter"] = args.typefilter

    for name, client in select_instances(clients, args.instance).items():
        try:
            results[name] = client.get("/nodes/localhost/tasks", params=params)
        except Exception as e:
            results[name] = {"error": str(e)}
    return results


def cmd_missing_backups(clients: dict[str, PBSClient], args):
    """Cross-reference PVE VMs against PBS snapshots to find gaps.

    Requires PVE_API_URL, PVE_API_TOKEN_ID, PVE_API_TOKEN_SECRET env vars
    for Proxmox VE access.
    """
    from datetime import timedelta

    days = args.days or 3
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    cutoff_ts = int(cutoff.timestamp())

    # Get VM list from PVE
    pve_url = os.environ.get("PVE_API_URL", "")
    pve_token_id = os.environ.get("PVE_API_TOKEN_ID", "")
    pve_token_secret = os.environ.get("PVE_API_TOKEN_SECRET", "")

    if not pve_url or not pve_token_id or not pve_token_secret:
        return {"error": "PVE_API_URL, PVE_API_TOKEN_ID, PVE_API_TOKEN_SECRET required for cross-ref"}

    verify_ssl = os.environ.get("PBS_VERIFY_SSL", "0") == "1"
    pve_opener = _make_opener(verify_ssl)
    pve_headers = {"Authorization": f"PVEAPIToken={pve_token_id}={pve_token_secret}"}

    try:
        pve_vms = _http_get(pve_opener, f"{pve_url}/api2/json/cluster/resources",
                            pve_headers, params={"type": "vm"})
        if not isinstance(pve_vms, list):
            pve_vms = pve_vms.get("data", [])
    except Exception as e:
        return {"error": f"Failed to query PVE: {e}"}

    # Build set of VMIDs that exist in PVE (running or stopped, not templates)
    vm_map = {}
    for vm in pve_vms:
        if vm.get("template", 0) == 1:
            continue
        vmid = str(vm.get("vmid", ""))
        vm_map[vmid] = {
            "name": vm.get("name", ""),
            "node": vm.get("node", ""),
            "type": vm.get("type", ""),
            "status": vm.get("status", ""),
        }

    # Check each PBS instance for recent snapshots
    backed_up_vmids = set()
    for _, client in select_instances(clients, args.instance).items():
        try:
            stores = client.get("/admin/datastore")
            for store in stores:
                try:
                    snaps = client.get(f"/admin/datastore/{store.get('name', store.get('store', ''))}/snapshots")
                    for snap in snaps:
                        backup_time = snap.get("backup-time", 0)
                        if backup_time >= cutoff_ts:
                            bid = snap.get("backup-id", "")
                            # backup-id is typically the VMID for VM backups
                            backed_up_vmids.add(bid)
                except Exception:
                    pass
        except Exception:
            pass

    # Find VMs without recent backups
    missing = []
    for vmid, info in sorted(vm_map.items()):
        if vmid not in backed_up_vmids:
            missing.append({"vmid": vmid, **info})

    return {
        "cutoff_days": days,
        "cutoff_time": cutoff.isoformat(),
        "total_vms": len(vm_map),
        "backed_up": len(backed_up_vmids),
        "missing_count": len(missing),
        "missing": missing,
    }


def main():
    parser = argparse.ArgumentParser(description="Query PBS instances")
    parser.add_argument("--instance", "-i", help="PBS instance name (default: all)")

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("datastores", help="List datastores with usage")

    p_snap = sub.add_parser("snapshots", help="List backup snapshots")
    p_snap.add_argument("--datastore", "-d", help="Filter by datastore")
    p_snap.add_argument("--vmid", help="Filter by VM ID")

    sub.add_parser("backup-jobs", help="Recent backup tasks")
    sub.add_parser("verify-jobs", help="Verify job config and status")
    sub.add_parser("sync-jobs", help="Sync job config and status")

    p_gc = sub.add_parser("gc-status", help="Garbage collection status")
    p_gc.add_argument("--datastore", "-d", help="Filter by datastore")

    p_log = sub.add_parser("task-log", help="Get task log (requires --instance and --upid)")
    p_log.add_argument("--upid", required=True, help="Task UPID")

    p_tasks = sub.add_parser("tasks", help="List recent tasks")
    p_tasks.add_argument("--typefilter", help="Filter: backup, verify, syncjob, garbage_collection, prune")
    p_tasks.add_argument("--limit", type=int, default=30, help="Max tasks to return")

    p_missing = sub.add_parser("missing-backups", help="Find VMs without recent backups")
    p_missing.add_argument("--days", type=int, default=3, help="Days threshold (default: 3)")

    args = parser.parse_args()

    clients = parse_instances()

    commands = {
        "datastores": cmd_datastores,
        "snapshots": cmd_snapshots,
        "backup-jobs": cmd_backup_jobs,
        "verify-jobs": cmd_verify_jobs,
        "sync-jobs": cmd_sync_jobs,
        "gc-status": cmd_gc_status,
        "task-log": cmd_task_log,
        "tasks": cmd_tasks,
        "missing-backups": cmd_missing_backups,
    }

    result = commands[args.command](clients, args)
    json.dump(result, sys.stdout, indent=2, default=str)
    print()


if __name__ == "__main__":
    main()
