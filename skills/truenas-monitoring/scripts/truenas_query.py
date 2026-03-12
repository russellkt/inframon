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


class AuthenticatedClient:
    """Wrapper that authenticates with API key on enter."""

    def __init__(self, uri, api_key, verify_ssl=False):
        self._uri = uri
        self._api_key = api_key
        self._verify_ssl = verify_ssl
        self._client = None

    def __enter__(self):
        self._client = Client(self._uri, verify_ssl=self._verify_ssl)
        c = self._client.__enter__()
        if not c.call("auth.login_with_api_key", self._api_key):
            raise RuntimeError("TrueNAS API key authentication failed")
        return c

    def __exit__(self, *args):
        return self._client.__exit__(*args)


def get_client():
    """Create an authenticated TrueNAS WebSocket client."""
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
    # TrueNAS WebSocket endpoint
    ws_url = f"{ws_url}/api/current"

    return AuthenticatedClient(ws_url, api_key, verify_ssl=False)


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
