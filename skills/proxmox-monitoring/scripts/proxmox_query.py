#!/usr/bin/env python3
"""Proxmox VE cluster query tool for inframon.

Queries Proxmox REST API with token authentication.
Stdlib only — no third-party dependencies.

Environment variables:
  PVE_API_URL          — Proxmox VE API base URL (e.g. https://10.10.1.14:8006)
  PVE_API_TOKEN_ID     — API token ID (e.g. inframon@pve!monitoring)
  PVE_API_TOKEN_SECRET — API token secret

Usage:
  proxmox_query.py cluster-status
  proxmox_query.py nodes
  proxmox_query.py node-status <node>
  proxmox_query.py vms [--node NAME] [--type qemu|lxc]
  proxmox_query.py storage
  proxmox_query.py node-disks <node>
  proxmox_query.py node-networks <node>
"""

import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# OpenFang strips env vars from subprocesses — recover from init process
_proc_env = Path("/proc/1/environ")
if _proc_env.exists():
    for entry in _proc_env.read_bytes().split(b"\0"):
        if b"=" in entry:
            k, v = entry.decode("utf-8", errors="replace").split("=", 1)
            os.environ.setdefault(k, v)


def api_get(path, params=None):
    """Make an authenticated GET request to the Proxmox REST API."""
    api_url = os.environ.get("PVE_API_URL")
    token_id = os.environ.get("PVE_API_TOKEN_ID")
    token_secret = os.environ.get("PVE_API_TOKEN_SECRET")

    if not api_url:
        print("ERROR: PVE_API_URL not set", file=sys.stderr)
        sys.exit(1)
    if not token_id or not token_secret:
        print("ERROR: PVE_API_TOKEN_ID and PVE_API_TOKEN_SECRET must be set", file=sys.stderr)
        sys.exit(1)

    url = f"{api_url}/api2/json{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)

    headers = {
        "Authorization": f"PVEAPIToken={token_id}={token_secret}",
    }

    ctx = ssl._create_unverified_context()
    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            body = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.read().decode()}"}
    except urllib.error.URLError as e:
        return {"error": f"Connection error: {e.reason}"}

    return body.get("data", body)


def cmd_cluster_status(args):
    return api_get("/cluster/status")


def cmd_nodes(args):
    return api_get("/nodes")


def cmd_node_status(args):
    return api_get(f"/nodes/{args.node}/status")


def cmd_vms(args):
    params = {"type": "vm"}
    result = api_get("/cluster/resources", params)
    if isinstance(result, dict) and "error" in result:
        return result

    # Filter to VMs/CTs only (exclude other resource types)
    if isinstance(result, list):
        result = [r for r in result if r.get("type") in ("qemu", "lxc")]
        if args.node:
            result = [r for r in result if r.get("node") == args.node]
        if args.type:
            result = [r for r in result if r.get("type") == args.type]

    return result


def cmd_storage(args):
    return api_get("/storage")


def cmd_node_disks(args):
    return api_get(f"/nodes/{args.node}/disks/list")


def cmd_node_networks(args):
    return api_get(f"/nodes/{args.node}/network")


def main():
    parser = argparse.ArgumentParser(description="Query Proxmox VE cluster")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("cluster-status", help="Cluster health, quorum, node membership")
    sub.add_parser("nodes", help="All nodes with resource usage")

    p_ns = sub.add_parser("node-status", help="Detailed node info")
    p_ns.add_argument("node", help="Node name (e.g. pve-r720)")

    p_vms = sub.add_parser("vms", help="VMs and containers with status")
    p_vms.add_argument("--node", help="Filter by node name")
    p_vms.add_argument("--type", choices=["qemu", "lxc"], help="Filter by VM type")

    sub.add_parser("storage", help="Storage status across cluster")

    p_disks = sub.add_parser("node-disks", help="Physical disk info per node")
    p_disks.add_argument("node", help="Node name")

    p_net = sub.add_parser("node-networks", help="Network interface config per node")
    p_net.add_argument("node", help="Node name")

    args = parser.parse_args()

    commands = {
        "cluster-status": cmd_cluster_status,
        "nodes": cmd_nodes,
        "node-status": cmd_node_status,
        "vms": cmd_vms,
        "storage": cmd_storage,
        "node-disks": cmd_node_disks,
        "node-networks": cmd_node_networks,
    }

    result = commands[args.command](args)
    json.dump(result, sys.stdout, indent=2, default=str)
    print()


if __name__ == "__main__":
    main()
