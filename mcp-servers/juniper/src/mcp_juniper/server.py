"""Juniper EX switch MCP server.

Provides real-time switch data via NETCONF (junos-eznc / PyEZ).
Exposes tools for interface status, alarms, LLDP, environment,
MAC table, chassis inventory, and routing info.

Credentials are read from environment variables:
  JUNIPER_USER     — Switch username (e.g. inframon)
  JUNIPER_PASSWORD  — Switch password
"""

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from fastmcp import FastMCP
from jnpr.junos import Device

# OpenFang strips env vars from MCP subprocess — recover from init process
_proc_env = Path("/proc/1/environ")
if _proc_env.exists():
    for entry in _proc_env.read_bytes().split(b"\0"):
        if b"=" in entry:
            k, v = entry.decode("utf-8", errors="replace").split("=", 1)
            os.environ.setdefault(k, v)

mcp = FastMCP("Juniper Switch MCP Server")

# Switch aliases — agent can use friendly names
SWITCH_ALIASES = {
    "ex3400": "10.10.1.10",
    "bmic-ex3400-1": "10.10.1.10",
    "ex2300": "10.10.1.9",
    "bmic-ex2300-1": "10.10.1.9",
}


def _resolve_host(host: str) -> str:
    """Resolve switch alias to IP address."""
    return SWITCH_ALIASES.get(host, host)


def _get_credentials() -> tuple[str, str]:
    """Get Juniper credentials from environment."""
    user = os.environ.get("JUNIPER_USER")
    password = os.environ.get("JUNIPER_PASSWORD")
    if not user or not password:
        raise RuntimeError("JUNIPER_USER and JUNIPER_PASSWORD must be set")
    return user, password


@contextmanager
def _connect(host: str):
    """Open a NETCONF session to a Juniper switch."""
    ip = _resolve_host(host)
    user, password = _get_credentials()
    dev = Device(host=ip, user=user, passwd=password, port=830, timeout=30)
    try:
        dev.open()
        yield dev
    finally:
        dev.close()


def _rpc_to_dict(element, strip_ns=True) -> dict:
    """Recursively convert an lxml RPC response to a dict.

    Strips Junos XML namespaces for cleaner output.
    """
    tag = element.tag
    if strip_ns and "}" in tag:
        tag = tag.split("}", 1)[1]

    result = {}

    if element.attrib:
        for k, v in element.attrib.items():
            if strip_ns and "}" in k:
                k = k.split("}", 1)[1]
            result["@" + k] = v

    children = list(element)
    if children:
        child_dict = {}
        for child in children:
            child_tag, child_val = list(_rpc_to_dict(child, strip_ns).items())[0]
            if child_tag in child_dict:
                if not isinstance(child_dict[child_tag], list):
                    child_dict[child_tag] = [child_dict[child_tag]]
                child_dict[child_tag].append(child_val)
            else:
                child_dict[child_tag] = child_val
        result.update(child_dict)
    elif element.text and element.text.strip():
        if not element.attrib:
            return {tag: element.text.strip()}
        result["#text"] = element.text.strip()

    if not result:
        return {tag: None}

    return {tag: result}


@mcp.tool()
def get_interfaces(
    host: str,
    interface_name: Optional[str] = None,
    terse: bool = False,
) -> dict:
    """Get interface status from a Juniper switch.

    Returns admin/oper status, traffic stats, and error counters.
    Use terse=true for a compact summary of all interfaces.
    Use interface_name to query a specific interface (e.g. ge-0/0/3).

    Host can be an IP or alias: ex3400 (10.10.1.10), ex2300 (10.10.1.9)
    """
    with _connect(host) as dev:
        kwargs = {}
        if interface_name:
            kwargs["interface_name"] = interface_name
        if terse:
            kwargs["terse"] = True
        resp = dev.rpc.get_interface_information(**kwargs)
        return _rpc_to_dict(resp)


@mcp.tool()
def get_alarms(host: str) -> dict:
    """Get active alarms from a Juniper switch.

    Returns alarm count, severity, timestamps, and descriptions.
    Use this to check for hardware or environmental issues.

    Host can be an IP or alias: ex3400 (10.10.1.10), ex2300 (10.10.1.9)
    """
    with _connect(host) as dev:
        resp = dev.rpc.get_alarm_information()
        return _rpc_to_dict(resp)


@mcp.tool()
def get_lldp_neighbors(host: str) -> dict:
    """Get LLDP neighbor discovery data from a Juniper switch.

    Shows what devices are connected to each port — useful for
    tracing physical connectivity and verifying cable/port assignments.

    Host can be an IP or alias: ex3400 (10.10.1.10), ex2300 (10.10.1.9)
    """
    with _connect(host) as dev:
        resp = dev.rpc.get_lldp_neighbors_information()
        return _rpc_to_dict(resp)


@mcp.tool()
def get_environment(host: str) -> dict:
    """Get environmental status from a Juniper switch.

    Returns temperature readings, fan status, and power supply health.
    Use this when investigating hardware alarms or thermal issues.

    Host can be an IP or alias: ex3400 (10.10.1.10), ex2300 (10.10.1.9)
    """
    with _connect(host) as dev:
        resp = dev.rpc.get_environment_information()
        return _rpc_to_dict(resp)


@mcp.tool()
def get_mac_table(host: str) -> dict:
    """Get the MAC address table (ethernet switching table) from a Juniper switch.

    Shows which MAC addresses are learned on which ports — useful for
    tracing where a device is connected on the network.

    Host can be an IP or alias: ex3400 (10.10.1.10), ex2300 (10.10.1.9)
    """
    with _connect(host) as dev:
        resp = dev.rpc.get_ethernet_switching_table_information()
        return _rpc_to_dict(resp)


@mcp.tool()
def get_chassis_inventory(host: str) -> dict:
    """Get hardware inventory from a Juniper switch.

    Returns model, serial numbers, and installed modules/transceivers.

    Host can be an IP or alias: ex3400 (10.10.1.10), ex2300 (10.10.1.9)
    """
    with _connect(host) as dev:
        resp = dev.rpc.get_chassis_inventory()
        return _rpc_to_dict(resp)


@mcp.tool()
def get_route_summary(host: str) -> dict:
    """Get routing table summary from a Juniper switch.

    Shows route counts per protocol and routing table. Useful for
    verifying routing health and detecting route leaks.

    Host can be an IP or alias: ex3400 (10.10.1.10), ex2300 (10.10.1.9)
    """
    with _connect(host) as dev:
        resp = dev.rpc.get_route_summary_information()
        return _rpc_to_dict(resp)


@mcp.tool()
def get_software_info(host: str) -> dict:
    """Get Junos software version and package information.

    Host can be an IP or alias: ex3400 (10.10.1.10), ex2300 (10.10.1.9)
    """
    with _connect(host) as dev:
        resp = dev.rpc.get_software_information()
        return _rpc_to_dict(resp)


@mcp.tool()
def get_vlans(host: str) -> dict:
    """Get VLAN configuration from a Juniper switch.

    Shows configured VLANs with names, IDs, and member interfaces.

    Host can be an IP or alias: ex3400 (10.10.1.10), ex2300 (10.10.1.9)
    """
    with _connect(host) as dev:
        resp = dev.rpc.get_vlan_information()
        return _rpc_to_dict(resp)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
