"""Zabbix monitoring MCP server.

Provides access to Zabbix 7.0 JSON-RPC API for monitoring data:
active problems, host status, item values, history, and event acknowledgment.

Credentials are read from environment variables:
  ZABBIX_API_URL   — Zabbix API endpoint (e.g. http://10.10.1.142/api_jsonrpc.php)
  ZABBIX_API_TOKEN — Zabbix API token for Bearer auth
"""

import os
from typing import Optional

from fastmcp import FastMCP
from pyzabbix import ZabbixAPI

mcp = FastMCP("Zabbix Monitoring MCP Server")


def _get_api() -> ZabbixAPI:
    """Create an authenticated Zabbix API client."""
    url = os.environ.get("ZABBIX_API_URL")
    token = os.environ.get("ZABBIX_API_TOKEN")
    if not url:
        raise RuntimeError("ZABBIX_API_URL must be set")
    if not token:
        raise RuntimeError("ZABBIX_API_TOKEN must be set")
    zapi = ZabbixAPI(url)
    zapi.login(api_token=token)
    return zapi


@mcp.tool()
def get_active_problems(
    severity_min: int = 0,
    limit: int = 20,
    host: Optional[str] = None,
) -> list[dict]:
    """Get active problems from Zabbix.

    Returns current unresolved problems sorted by most recent first.
    Use severity_min to filter (0=all, 2=warning+, 3=average+, 4=high+, 5=disaster).
    Use host to filter by hostname (e.g. 'ex3400', 'pve-r720').

    Severity levels: 0=Not classified, 1=Info, 2=Warning, 3=Average, 4=High, 5=Disaster
    """
    zapi = _get_api()
    params = {
        "output": "extend",
        "recent": True,
        "sortfield": "eventid",
        "sortorder": "DESC",
        "limit": limit,
    }
    if severity_min > 0:
        params["severities"] = list(range(severity_min, 6))
    if host:
        # Look up hostid by name
        hosts = zapi.host.get(filter={"host": host}, output=["hostid"])
        if hosts:
            params["hostids"] = [hosts[0]["hostid"]]
    return zapi.problem.get(**params)


@mcp.tool()
def get_unacknowledged_problems(
    severity_min: int = 2,
    limit: int = 10,
) -> list[dict]:
    """Get unacknowledged problems — issues the agent hasn't processed yet.

    Defaults to severity >= Warning (2). These are problems that need investigation.

    Severity levels: 2=Warning, 3=Average, 4=High, 5=Disaster
    """
    zapi = _get_api()
    return zapi.problem.get(
        output="extend",
        recent=True,
        acknowledged=False,
        severities=list(range(severity_min, 6)),
        sortfield="eventid",
        sortorder="DESC",
        limit=limit,
    )


@mcp.tool()
def get_hosts() -> list[dict]:
    """Get all monitored hosts from Zabbix.

    Returns hostid, hostname, display name, status, and IP addresses.
    Status: 0=enabled, 1=disabled.
    """
    zapi = _get_api()
    return zapi.host.get(
        output=["hostid", "host", "name", "status"],
        selectInterfaces=["ip"],
    )


@mcp.tool()
def get_host_items(
    host: str,
    search: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """Get monitored items (metrics) for a specific host.

    Use search to filter by item name (e.g. 'CPU', 'ifOperStatus', 'memory').
    Returns item name, last value, units, and last update time.

    Common hosts: ex3400 (hostid 10595), ex2300 (10594), pve-r720 (10596)
    """
    zapi = _get_api()
    # Look up hostid by name
    hosts = zapi.host.get(filter={"host": host}, output=["hostid"])
    if not hosts:
        return [{"error": f"Host '{host}' not found"}]
    hostid = hosts[0]["hostid"]

    params = {
        "hostids": [hostid],
        "output": ["name", "lastvalue", "units", "lastclock", "key_"],
        "sortfield": "name",
        "limit": limit,
    }
    if search:
        params["search"] = {"name": search}
    return zapi.item.get(**params)


@mcp.tool()
def get_history(
    itemid: str,
    history_type: int = 0,
    limit: int = 10,
) -> list[dict]:
    """Get historical values for a specific item.

    Use after get_host_items to drill into a metric's recent values.
    history_type: 0=float, 1=string, 2=log, 3=integer, 4=text

    Returns timestamped values sorted newest first.
    """
    zapi = _get_api()
    return zapi.history.get(
        itemids=[itemid],
        output="extend",
        history=history_type,
        sortfield="clock",
        sortorder="DESC",
        limit=limit,
    )


@mcp.tool()
def get_triggers(
    host: str,
    only_problems: bool = True,
) -> list[dict]:
    """Get triggers for a host — shows alert conditions and their current state.

    Use only_problems=true (default) to see only active triggers.
    Returns trigger description, severity, and last change time.
    """
    zapi = _get_api()
    hosts = zapi.host.get(filter={"host": host}, output=["hostid"])
    if not hosts:
        return [{"error": f"Host '{host}' not found"}]
    hostid = hosts[0]["hostid"]

    params = {
        "hostids": [hostid],
        "output": ["description", "priority", "value", "lastchange"],
    }
    if only_problems:
        params["only_true"] = True
    return zapi.trigger.get(**params)


@mcp.tool()
def acknowledge_event(
    event_id: str,
    message: str,
) -> dict:
    """Acknowledge a Zabbix event and add an investigation message.

    Call this after investigating a problem to mark it as handled and
    record your findings. The message should summarize what was checked
    and what was found.
    """
    zapi = _get_api()
    # action=6 = acknowledge + add message
    return zapi.event.acknowledge(
        eventids=[event_id],
        action=6,
        message=f"[inframon] {message}",
    )


@mcp.tool()
def get_problem_details(
    event_id: str,
) -> list[dict]:
    """Get detailed information about a specific problem by event ID.

    Use this when a webhook alert arrives with an event_id to get
    full context about the problem.
    """
    zapi = _get_api()
    return zapi.problem.get(
        eventids=[event_id],
        output="extend",
        selectTags="extend",
    )


def main():
    mcp.run()


if __name__ == "__main__":
    main()
