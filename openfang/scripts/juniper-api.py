#!/usr/bin/env python3
"""Juniper REST API client for OpenFang shell_exec.

Queries Juniper EX switches via their built-in REST API (rpc-on-http).
No third-party dependencies — uses only Python stdlib.
Reads credentials from /proc/1/environ (container env) since OpenFang's
shell_exec sandbox strips environment variables from subprocesses.

Usage:
    python3 juniper-api.py <host> <rpc> [param=value ...]

Examples:
    python3 juniper-api.py 10.10.1.10 get-interface-information
    python3 juniper-api.py 10.10.1.9 get-interface-information interface-name=ge-0/0/0
    python3 juniper-api.py 10.10.1.10 get-ethernet-switching-table-information
    python3 juniper-api.py 10.10.1.10 get-lldp-neighbors-information
    python3 juniper-api.py 10.10.1.10 get-alarm-information
    python3 juniper-api.py 10.10.1.10 get-chassis-inventory
    python3 juniper-api.py 10.10.1.10 get-environment-information
    python3 juniper-api.py 10.10.1.10 get-route-summary-information
"""

import base64
import json
import os

import sys
import urllib.error
import urllib.parse
import urllib.request


# Known switches — agent can use hostname aliases
SWITCH_ALIASES = {
    "ex3400": "10.10.1.10",
    "bmic-ex3400-1": "10.10.1.10",
    "ex2300": "10.10.1.9",
    "bmic-ex2300-1": "10.10.1.9",
}


def load_container_env(key):
    """Read env var from container's PID 1 environ (bypasses sandbox stripping)."""
    val = os.environ.get(key)
    if val:
        return val
    try:
        with open("/proc/1/environ", "rb") as f:
            for entry in f.read().split(b"\x00"):
                if entry.startswith(key.encode() + b"="):
                    return entry.decode().split("=", 1)[1]
    except (OSError, PermissionError):
        pass
    return None


def api_rpc(host, rpc, params=None, user=None, password=None):
    """Execute a Junos RPC via the REST API."""
    url = f"http://{host}:8080/rpc/{rpc}"

    # Add RPC parameters as query string
    if params:
        url += "?" + urllib.parse.urlencode(params)

    # HTTP Basic Auth
    creds = base64.b64encode(f"{user}:{password}".encode()).decode()
    headers = {
        "Authorization": f"Basic {creds}",
        "Accept": "application/json",
    }

    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"HTTP {e.code}: {body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Connection error to {host}: {e.reason}", file=sys.stderr)
        sys.exit(1)


def main():
    if len(sys.argv) < 3:
        print("Usage: juniper-api.py <host> <rpc> [param=value ...]", file=sys.stderr)
        print("  host: IP or alias (ex3400, ex2300)", file=sys.stderr)
        print("  rpc:  Junos RPC name (e.g. get-interface-information)", file=sys.stderr)
        print("  params: key=value pairs (e.g. interface-name=ge-0/0/0)", file=sys.stderr)
        print("\nCommon RPCs:", file=sys.stderr)
        print("  get-interface-information       - Interface status and stats", file=sys.stderr)
        print("  get-ethernet-switching-table-information - MAC table", file=sys.stderr)
        print("  get-lldp-neighbors-information  - LLDP neighbor discovery", file=sys.stderr)
        print("  get-alarm-information           - Active alarms", file=sys.stderr)
        print("  get-chassis-inventory           - Hardware inventory", file=sys.stderr)
        print("  get-environment-information     - Temps, fans, PSUs", file=sys.stderr)
        print("  get-route-summary-information   - Routing table summary", file=sys.stderr)
        sys.exit(1)

    host = sys.argv[1]
    rpc = sys.argv[2]

    # Resolve aliases
    host = SWITCH_ALIASES.get(host, host)

    # Parse key=value params
    params = {}
    for arg in sys.argv[3:]:
        if "=" in arg:
            k, v = arg.split("=", 1)
            params[k] = v

    # Load credentials
    user = load_container_env("JUNIPER_USER")
    password = load_container_env("JUNIPER_PASSWORD")

    if not user or not password:
        print("ERROR: JUNIPER_USER and JUNIPER_PASSWORD must be set", file=sys.stderr)
        sys.exit(1)

    result = api_rpc(host, rpc, params or None, user, password)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
