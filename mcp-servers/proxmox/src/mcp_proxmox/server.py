"""Proxmox VE cluster MCP server.

Provides access to the Proxmox REST API for cluster status, node health,
VM/container management, and storage monitoring.

Credentials are read from environment variables:
  PVE_API_URL          — Proxmox API URL (e.g. https://10.10.1.14:8006)
  PVE_API_TOKEN_ID     — API token ID (e.g. inframon@pam!monitoring)
  PVE_API_TOKEN_SECRET — API token secret (UUID)
"""

import os
import urllib3
from typing import Optional

from fastmcp import FastMCP
from proxmoxer import ProxmoxAPI

# Suppress InsecureRequestWarning for self-signed certs
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

mcp = FastMCP("Proxmox VE MCP Server")


def _get_api() -> ProxmoxAPI:
    """Create an authenticated Proxmox API client."""
    url = os.environ.get("PVE_API_URL")
    token_id = os.environ.get("PVE_API_TOKEN_ID")
    token_secret = os.environ.get("PVE_API_TOKEN_SECRET")
    if not url or not token_id or not token_secret:
        raise RuntimeError("PVE_API_URL, PVE_API_TOKEN_ID, and PVE_API_TOKEN_SECRET must be set")

    # Parse host and port from URL
    # e.g. https://10.10.1.14:8006 -> host=10.10.1.14, port=8006
    from urllib.parse import urlparse
    parsed = urlparse(url)
    host = parsed.hostname
    port = parsed.port or 8006

    return ProxmoxAPI(
        host,
        port=port,
        user=token_id.split("!")[0],
        token_name=token_id.split("!")[1],
        token_value=token_secret,
        verify_ssl=False,
        timeout=30,
    )


@mcp.tool()
def get_cluster_status() -> list[dict]:
    """Get Proxmox cluster status.

    Returns cluster health, quorum status, and node membership.
    Use this for a quick overview of cluster health.
    """
    api = _get_api()
    return api.cluster.status.get()


@mcp.tool()
def get_nodes() -> list[dict]:
    """Get all Proxmox cluster nodes with resource usage.

    Returns CPU, memory, disk usage, uptime, and online status for each node.
    """
    api = _get_api()
    return api.nodes.get()


@mcp.tool()
def get_node_status(node: str) -> dict:
    """Get detailed status of a specific Proxmox node.

    Returns CPU model, core count, memory breakdown, kernel version,
    uptime, and current load.

    Common nodes: pve-r720, pve-p520, pve-z2, pve5820gpu
    """
    api = _get_api()
    return api.nodes(node).status.get()


@mcp.tool()
def get_vms(
    node: Optional[str] = None,
    vm_type: Optional[str] = None,
) -> list[dict]:
    """Get VMs and containers across the cluster.

    Returns VMID, name, status, node, CPU/memory allocation for each.
    Use vm_type='vm' for VMs only, 'lxc' for containers only, or omit for all.
    Use node to filter by a specific node.
    """
    api = _get_api()
    params = {}
    if vm_type:
        params["type"] = vm_type
    resources = api.cluster.resources.get(**params) if not params else api.cluster.resources.get(type=vm_type)

    # Filter to VMs/containers only (exclude storage, node entries)
    if not vm_type:
        resources = [r for r in resources if r.get("type") in ("qemu", "lxc")]

    if node:
        resources = [r for r in resources if r.get("node") == node]

    return resources


@mcp.tool()
def get_storage() -> list[dict]:
    """Get storage status across the cluster.

    Returns storage name, type, total/used/available space, and which nodes have access.
    """
    api = _get_api()
    return api.storage.get()


@mcp.tool()
def get_node_disks(node: str) -> list[dict]:
    """Get disk information for a Proxmox node.

    Returns physical disks with model, serial, size, and health status.

    Common nodes: pve-r720, pve-p520, pve-z2, pve5820gpu
    """
    api = _get_api()
    return api.nodes(node).disks.list.get()


@mcp.tool()
def get_node_networks(node: str) -> list[dict]:
    """Get network interfaces for a Proxmox node.

    Returns bridge, bond, and physical interface configuration.
    """
    api = _get_api()
    return api.nodes(node).network.get()


def main():
    mcp.run()


if __name__ == "__main__":
    main()
