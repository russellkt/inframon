#!/usr/bin/env python3
"""Proxmox query helper for OpenFang shell_exec.

Runs pvesh commands on pve-r720 via SSH (key auth).
No third-party dependencies — uses only Python stdlib.

Usage:
    python3 proxmox-query.py <pvesh-path> [--type TYPE]

Examples:
    python3 proxmox-query.py /nodes
    python3 proxmox-query.py /cluster/status
    python3 proxmox-query.py /cluster/resources --type vm
    python3 proxmox-query.py /nodes/pve-r720/status
    python3 proxmox-query.py zpool-status
    python3 proxmox-query.py zpool-list
"""

import json
import subprocess
import sys

PVE_HOST = "root@10.10.1.14"
SSH_OPTS = ["-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10", "-o", "BatchMode=yes"]


def ssh_cmd(command: str) -> str:
    """Run a command on pve-r720 via SSH."""
    result = subprocess.run(
        ["ssh"] + SSH_OPTS + [PVE_HOST, command],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        print(f"SSH error: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip()


def main():
    if len(sys.argv) < 2:
        print("Usage: proxmox-query.py <path> [--type TYPE]", file=sys.stderr)
        print("  path: pvesh API path (e.g. /nodes, /cluster/status)", file=sys.stderr)
        print("  Special paths: zpool-status, zpool-list, ping <ip>", file=sys.stderr)
        sys.exit(1)

    path = sys.argv[1]

    # Special non-pvesh commands
    if path == "zpool-status":
        print(ssh_cmd("zpool status"))
        return
    if path == "zpool-list":
        print(ssh_cmd("zpool list"))
        return
    if path == "ping":
        target = sys.argv[2] if len(sys.argv) > 2 else ""
        if not target:
            print("Usage: proxmox-query.py ping <ip>", file=sys.stderr)
            sys.exit(1)
        print(ssh_cmd(f"ping -c 3 -W 2 {target}"))
        return

    # Build pvesh command
    cmd = f"pvesh get {path} --output-format json"

    # Handle --type flag
    if "--type" in sys.argv:
        idx = sys.argv.index("--type")
        if idx + 1 < len(sys.argv):
            cmd = f"pvesh get {path} --type {sys.argv[idx + 1]} --output-format json"

    output = ssh_cmd(cmd)

    # Pretty-print JSON output
    try:
        data = json.loads(output)
        print(json.dumps(data, indent=2))
    except json.JSONDecodeError:
        print(output)


if __name__ == "__main__":
    main()
