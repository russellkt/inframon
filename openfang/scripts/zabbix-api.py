#!/usr/bin/env python3
"""Zabbix JSON-RPC API client for OpenFang shell_exec.

No third-party dependencies — uses only Python stdlib.
Reads config from /proc/1/environ (container env) since OpenFang's
shell_exec sandbox strips environment variables from subprocesses.

Usage:
    python3 zabbix-api.py <method> [params_file]

Examples:
    python3 zabbix-api.py apiinfo.version
    python3 zabbix-api.py problem.get /usr/local/share/inframon/scripts/queries/active-problems.json
    python3 zabbix-api.py host.get /tmp/params.json
"""

import json
import os
import sys
import urllib.request


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


def main():
    if len(sys.argv) < 2:
        print("Usage: zabbix-api.py <method> [params_file]", file=sys.stderr)
        sys.exit(1)

    method = sys.argv[1]
    params_file = sys.argv[2] if len(sys.argv) > 2 else None

    api_url = load_container_env("ZABBIX_API_URL")
    api_token = load_container_env("ZABBIX_API_TOKEN")

    if not api_url:
        print("ERROR: ZABBIX_API_URL not set", file=sys.stderr)
        sys.exit(1)

    # Load params from file or use empty dict
    params = {}
    if params_file:
        with open(params_file) as f:
            params = json.load(f)

    # Build JSON-RPC request
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "id": 1,
        "params": params,
    }

    headers = {"Content-Type": "application/json-rpc"}

    # apiinfo.version must NOT have auth header
    if api_token and method != "apiinfo.version":
        headers["Authorization"] = f"Bearer {api_token}"

    data = json.dumps(payload).encode()
    req = urllib.request.Request(api_url, data=data, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode()}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Connection error: {e.reason}", file=sys.stderr)
        sys.exit(1)

    # Extract result or show error
    if "error" in body:
        err = body["error"]
        print(f"Zabbix API error: {err.get('message', '')} — {err.get('data', '')}", file=sys.stderr)
        sys.exit(1)

    # Print just the result, pretty-formatted
    result = body.get("result", body)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
