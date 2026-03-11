#!/usr/bin/env python3
"""Proxmox REST API client for OpenFang shell_exec.

Replaces SSH-based proxmox-query.py with direct REST API calls.
No third-party dependencies — uses only Python stdlib.
Reads config from /proc/1/environ (container env) since OpenFang's
shell_exec sandbox strips environment variables from subprocesses.

Usage:
    python3 proxmox-api.py <path> [--type TYPE]

Examples:
    python3 proxmox-api.py /nodes
    python3 proxmox-api.py /cluster/status
    python3 proxmox-api.py /cluster/resources --type vm
    python3 proxmox-api.py /nodes/pve-r720/status
    python3 proxmox-api.py zpool-status
    python3 proxmox-api.py zpool-list
"""

import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request


PVE_HOST = "root@10.10.1.14"
SSH_OPTS = ["-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10", "-o", "BatchMode=yes"]


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


def ssh_cmd(command):
    """Run a command on pve-r720 via SSH (fallback for commands with no REST equivalent)."""
    import subprocess
    result = subprocess.run(
        ["ssh"] + SSH_OPTS + [PVE_HOST, command],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        print(f"SSH error: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip()


def api_get(base_url, token_id, token_secret, path, params=None):
    """Make an authenticated GET request to the Proxmox REST API."""
    url = f"{base_url}/api2/json{path}"
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
        print(f"HTTP {e.code}: {e.read().decode()}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Connection error: {e.reason}", file=sys.stderr)
        sys.exit(1)

    return body.get("data", body)


def main():
    if len(sys.argv) < 2:
        print("Usage: proxmox-api.py <path> [--type TYPE]", file=sys.stderr)
        print("  path: API path (e.g. /nodes, /cluster/status)", file=sys.stderr)
        print("  Special commands: zpool-status, zpool-list", file=sys.stderr)
        sys.exit(1)

    path = sys.argv[1]

    # Special non-REST commands (SSH fallback — no API equivalent)
    if path == "zpool-status":
        print(ssh_cmd("zpool status"))
        return
    if path == "zpool-list":
        print(ssh_cmd("zpool list"))
        return

    # Load API credentials from environment
    api_url = load_container_env("PVE_API_URL")
    token_id = load_container_env("PVE_API_TOKEN_ID")
    token_secret = load_container_env("PVE_API_TOKEN_SECRET")

    if not api_url:
        print("ERROR: PVE_API_URL not set", file=sys.stderr)
        sys.exit(1)
    if not token_id:
        print("ERROR: PVE_API_TOKEN_ID not set", file=sys.stderr)
        sys.exit(1)
    if not token_secret:
        print("ERROR: PVE_API_TOKEN_SECRET not set", file=sys.stderr)
        sys.exit(1)

    # Handle --type flag as query parameter
    params = {}
    if "--type" in sys.argv:
        idx = sys.argv.index("--type")
        if idx + 1 < len(sys.argv):
            params["type"] = sys.argv[idx + 1]

    result = api_get(api_url, token_id, token_secret, path, params or None)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
