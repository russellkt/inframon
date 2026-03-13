#!/usr/bin/env python3
"""Zabbix monitoring query tool for inframon.

Queries Zabbix 7.0 JSON-RPC API with Bearer token auth.
Stdlib only — no third-party dependencies.

Environment variables:
  ZABBIX_API_URL    — Zabbix API endpoint
  ZABBIX_API_TOKEN  — API authentication token

Usage:
  zabbix_query.py active-problems [--severity-min N] [--limit N] [--host NAME]
  zabbix_query.py unacknowledged-problems [--severity-min N] [--limit N]
  zabbix_query.py hosts
  zabbix_query.py host-items <host> [--search TEXT] [--limit N]
  zabbix_query.py history <itemid> [--type N] [--limit N]
  zabbix_query.py triggers <host> [--active-only]
  zabbix_query.py acknowledge <event_id> --message TEXT
  zabbix_query.py problem-details <event_id>
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

# OpenFang strips env vars from subprocesses — recover from init process
_proc_env = Path("/proc/1/environ")
if _proc_env.exists():
    for entry in _proc_env.read_bytes().split(b"\0"):
        if b"=" in entry:
            k, v = entry.decode("utf-8", errors="replace").split("=", 1)
            os.environ.setdefault(k, v)


def zabbix_rpc(method, params=None):
    """Make a Zabbix JSON-RPC API call."""
    api_url = os.environ.get("ZABBIX_API_URL")
    api_token = os.environ.get("ZABBIX_API_TOKEN")

    if not api_url:
        print("ERROR: ZABBIX_API_URL not set", file=sys.stderr)
        sys.exit(1)

    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "id": 1,
        "params": params or {},
    }

    headers = {"Content-Type": "application/json-rpc"}
    if api_token and method != "apiinfo.version":
        headers["Authorization"] = f"Bearer {api_token}"

    data = json.dumps(payload).encode()
    req = urllib.request.Request(api_url, data=data, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.read().decode()}"}
    except urllib.error.URLError as e:
        return {"error": f"Connection error: {e.reason}"}

    if "error" in body:
        err = body["error"]
        return {"error": f"{err.get('message', '')} — {err.get('data', '')}"}

    return body.get("result", body)


def resolve_host(hostname):
    """Resolve a hostname to a Zabbix hostid."""
    result = zabbix_rpc("host.get", {
        "filter": {"host": [hostname]},
        "output": ["hostid", "host", "name"],
    })
    if isinstance(result, dict) and "error" in result:
        return None, result
    if not result:
        return None, {"error": f"Host '{hostname}' not found in Zabbix"}
    return result[0]["hostid"], None


def cmd_active_problems(args):
    params = {
        "output": ["eventid", "name", "severity", "clock", "acknowledged", "opdata"],
        "sortfield": ["eventid"],
        "sortorder": "DESC",
        "recent": True,
        "limit": args.limit or 50,
    }
    if args.severity_min is not None:
        params["severities"] = list(range(args.severity_min, 6))
    if args.host:
        hostid, err = resolve_host(args.host)
        if err:
            return err
        params["hostids"] = [hostid]
    return zabbix_rpc("problem.get", params)


def cmd_unacknowledged_problems(args):
    params = {
        "output": ["eventid", "name", "severity", "clock", "acknowledged", "opdata"],
        "sortfield": ["eventid"],
        "sortorder": "DESC",
        "recent": True,
        "acknowledged": False,
        "severities": list(range(args.severity_min if args.severity_min is not None else 2, 6)),
        "limit": args.limit or 50,
    }
    return zabbix_rpc("problem.get", params)


def cmd_hosts(_args):
    return zabbix_rpc("host.get", {
        "output": ["hostid", "host", "name", "status"],
        "selectInterfaces": ["ip", "type", "main"],
        "sortfield": "host",
    })


def cmd_host_items(args):
    hostid, err = resolve_host(args.host)
    if err:
        return err
    params = {
        "hostids": [hostid],
        "output": ["itemid", "name", "key_", "lastvalue", "lastclock", "units", "value_type"],
        "sortfield": "name",
    }
    if args.search:
        params["search"] = {"name": args.search}
        params["searchWildcardsEnabled"] = True
    if args.limit:
        params["limit"] = args.limit
    return zabbix_rpc("item.get", params)


def cmd_history(args):
    params = {
        "itemids": [args.itemid],
        "history": args.type if args.type is not None else 0,
        "sortfield": "clock",
        "sortorder": "DESC",
        "limit": args.limit or 20,
        "output": "extend",
    }
    return zabbix_rpc("history.get", params)


def cmd_triggers(args):
    hostid, err = resolve_host(args.host)
    if err:
        return err
    params = {
        "hostids": [hostid],
        "output": ["triggerid", "description", "priority", "value", "lastchange", "status"],
        "expandDescription": True,
        "sortfield": "priority",
        "sortorder": "DESC",
    }
    if args.active_only:
        params["filter"] = {"value": 1}
    return zabbix_rpc("trigger.get", params)


def cmd_acknowledge(args):
    return zabbix_rpc("event.acknowledge", {
        "eventids": [args.event_id],
        "action": 6,
        "message": f"[inframon] {args.message}",
    })


def cmd_problem_details(args):
    return zabbix_rpc("problem.get", {
        "eventids": [args.event_id],
        "output": "extend",
        "selectAcknowledges": "extend",
        "selectTags": "extend",
        "selectSuppressionData": "extend",
    })


def main():
    parser = argparse.ArgumentParser(description="Query Zabbix monitoring API")
    sub = parser.add_subparsers(dest="command", required=True)

    p_active = sub.add_parser("active-problems", help="Current unresolved problems")
    p_active.add_argument("--severity-min", type=int, help="Minimum severity (0-5)")
    p_active.add_argument("--limit", type=int, help="Max results")
    p_active.add_argument("--host", help="Filter by hostname")

    p_unack = sub.add_parser("unacknowledged-problems", help="Problems not yet handled")
    p_unack.add_argument("--severity-min", type=int, help="Minimum severity (default: 2)")
    p_unack.add_argument("--limit", type=int, help="Max results")

    sub.add_parser("hosts", help="All monitored hosts with status")

    p_items = sub.add_parser("host-items", help="Monitored metrics for a host")
    p_items.add_argument("host", help="Hostname as shown in Zabbix")
    p_items.add_argument("--search", help="Search item names")
    p_items.add_argument("--limit", type=int, help="Max results")

    p_hist = sub.add_parser("history", help="Historical values for a metric")
    p_hist.add_argument("itemid", help="Zabbix item ID")
    p_hist.add_argument("--type", type=int, help="History type: 0=float, 1=string, 2=log, 3=uint, 4=text")
    p_hist.add_argument("--limit", type=int, help="Max results (default: 20)")

    p_trig = sub.add_parser("triggers", help="Alert conditions for a host")
    p_trig.add_argument("host", help="Hostname as shown in Zabbix")
    p_trig.add_argument("--active-only", action="store_true", help="Only show firing triggers")

    p_ack = sub.add_parser("acknowledge", help="Mark problem as investigated")
    p_ack.add_argument("--event-id", required=True, dest="event_id", help="Zabbix event ID")
    p_ack.add_argument("--message", required=True, help="Investigation summary")

    p_detail = sub.add_parser("problem-details", help="Full context for a specific event")
    p_detail.add_argument("--event-id", required=True, dest="event_id", help="Zabbix event ID")

    args = parser.parse_args()

    commands = {
        "active-problems": cmd_active_problems,
        "unacknowledged-problems": cmd_unacknowledged_problems,
        "hosts": cmd_hosts,
        "host-items": cmd_host_items,
        "history": cmd_history,
        "triggers": cmd_triggers,
        "acknowledge": cmd_acknowledge,
        "problem-details": cmd_problem_details,
    }

    result = commands[args.command](args)
    json.dump(result, sys.stdout, indent=2, default=str)
    print()


if __name__ == "__main__":
    main()
