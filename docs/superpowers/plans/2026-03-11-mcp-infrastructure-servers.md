# Infrastructure MCP Servers Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace shell_exec Python scripts with three FastMCP servers (Juniper, Zabbix, Proxmox) that give the OpenFang agent typed, self-describing tools with real pip dependencies.

**Architecture:** Each MCP server is a standalone Python package in `mcp-servers/<name>/`, runnable via `uvx` over stdio transport. FastMCP handles tool registration, schema generation, and transport. OpenFang spawns each server as a child process via `[[mcp_servers]]` in config.toml. The agent discovers tools automatically — no system prompt documentation needed for tool usage.

**Tech Stack:** Python 3.11+, FastMCP, uv/uvx, junos-eznc (PyEZ), pyzabbix, proxmoxer

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `mcp-servers/juniper/pyproject.toml` | Create | Package config, deps (fastmcp, junos-eznc) |
| `mcp-servers/juniper/src/mcp_juniper/__init__.py` | Create | Package init |
| `mcp-servers/juniper/src/mcp_juniper/server.py` | Create | FastMCP server with Juniper tools |
| `mcp-servers/zabbix/pyproject.toml` | Create | Package config, deps (fastmcp, pyzabbix) |
| `mcp-servers/zabbix/src/mcp_zabbix/__init__.py` | Create | Package init |
| `mcp-servers/zabbix/src/mcp_zabbix/server.py` | Create | FastMCP server with Zabbix tools |
| `mcp-servers/proxmox/pyproject.toml` | Create | Package config, deps (fastmcp, proxmoxer) |
| `mcp-servers/proxmox/src/mcp_proxmox/__init__.py` | Create | Package init |
| `mcp-servers/proxmox/src/mcp_proxmox/server.py` | Create | FastMCP server with Proxmox tools |
| `openfang/config.toml` | Modify | Add all three MCP servers |
| `openfang/agents/inframon/agent.toml` | Modify | Slim down system prompt (remove tool docs, keep investigation logic) |
| `docker-compose.openfang.yml` | Modify | Mount mcp-servers directory |
| `Dockerfile.openfang` | Modify | Pre-install MCP server deps for fast startup |

---

## Chunk 1: Juniper MCP Server

### Task 1: Create Juniper MCP Server Package

**Files:**
- Create: `mcp-servers/juniper/pyproject.toml`
- Create: `mcp-servers/juniper/src/mcp_juniper/__init__.py`
- Create: `mcp-servers/juniper/src/mcp_juniper/server.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "mcp-juniper"
version = "0.1.0"
description = "Juniper EX switch MCP server for infrastructure monitoring"
requires-python = ">=3.10"
dependencies = [
    "fastmcp>=2.0",
    "junos-eznc>=2.7",
]

[project.scripts]
mcp-juniper = "mcp_juniper.server:main"
```

- [ ] **Step 2: Create package init**

```python
# mcp-servers/juniper/src/mcp_juniper/__init__.py
```

(Empty file — just marks as package.)

- [ ] **Step 3: Write the MCP server**

```python
# mcp-servers/juniper/src/mcp_juniper/server.py
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
from typing import Optional

from fastmcp import FastMCP
from jnpr.junos import Device
from jnpr.junos.exception import ConnectError, RpcError
from lxml import etree

mcp = FastMCP(
    "Juniper Switch MCP Server",
    description="Query Juniper EX switches for real-time interface, alarm, LLDP, and environment data.",
)

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


def _xml_to_text(element) -> str:
    """Convert lxml element to indented XML string."""
    return etree.tostring(element, pretty_print=True, encoding="unicode")


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
```

- [ ] **Step 4: Test locally**

```bash
cd mcp-servers/juniper
JUNIPER_USER=inframon JUNIPER_PASSWORD='inframon123\!' uv run mcp-juniper
```

This starts the stdio server. Press Ctrl+C to stop. If it starts without errors, the server loads correctly.

- [ ] **Step 5: Commit**

```bash
git add mcp-servers/juniper/
git commit -m "feat: add Juniper MCP server with PyEZ/NETCONF"
```

---

### Task 2: Wire Juniper MCP into OpenFang and Test

**Files:**
- Modify: `openfang/config.toml`
- Modify: `docker-compose.openfang.yml`
- Modify: `Dockerfile.openfang`

- [ ] **Step 1: Mount mcp-servers into container**

In `docker-compose.openfang.yml`, add a volume mount after the scripts mount:

```yaml
      - ./mcp-servers:/usr/local/share/inframon/mcp-servers:ro
```

- [ ] **Step 2: Pre-install Juniper MCP deps in Dockerfile**

In `Dockerfile.openfang`, after the uv install line, add:

```dockerfile
# Pre-install MCP server dependencies for fast startup
COPY mcp-servers/juniper /tmp/mcp-juniper
RUN cd /tmp/mcp-juniper && uv sync && rm -rf /tmp/mcp-juniper
```

Note: This pre-populates uv's cache so `uvx` doesn't download deps on every container start. The actual server code is mounted from the host via the volume (so code changes don't require rebuilds).

- [ ] **Step 3: Add Juniper MCP to config.toml**

Add after the existing `[[mcp_servers]]` fetch entry:

```toml
[[mcp_servers]]
name = "juniper"
timeout_secs = 30

[mcp_servers.transport]
type = "stdio"
command = "uvx"
args = ["--directory", "/usr/local/share/inframon/mcp-servers/juniper", "mcp-juniper"]
```

- [ ] **Step 4: Rebuild and verify**

```bash
docker compose -f docker-compose.openfang.yml up -d --build
```

Check logs for:
```
MCP server connected  server=juniper  tools=9
```

- [ ] **Step 5: Test from dashboard**

Open http://localhost:4200 and ask the agent:
> "Check the alarms on the ex3400 switch"

Verify the agent calls the `get_alarms` MCP tool (not the old shell_exec script).

- [ ] **Step 6: Commit**

```bash
git add openfang/config.toml docker-compose.openfang.yml Dockerfile.openfang
git commit -m "feat: wire Juniper MCP server into OpenFang"
```

---

## Chunk 2: Zabbix MCP Server

### Task 3: Create Zabbix MCP Server Package

**Files:**
- Create: `mcp-servers/zabbix/pyproject.toml`
- Create: `mcp-servers/zabbix/src/mcp_zabbix/__init__.py`
- Create: `mcp-servers/zabbix/src/mcp_zabbix/server.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "mcp-zabbix"
version = "0.1.0"
description = "Zabbix monitoring MCP server for infrastructure monitoring"
requires-python = ">=3.10"
dependencies = [
    "fastmcp>=2.0",
    "pyzabbix>=1.3",
]

[project.scripts]
mcp-zabbix = "mcp_zabbix.server:main"
```

- [ ] **Step 2: Create package init**

```python
# mcp-servers/zabbix/src/mcp_zabbix/__init__.py
```

- [ ] **Step 3: Write the MCP server**

```python
# mcp-servers/zabbix/src/mcp_zabbix/server.py
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

mcp = FastMCP(
    "Zabbix Monitoring MCP Server",
    description="Query Zabbix 7.0 for active problems, host status, metrics, history, and event management.",
)


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
```

- [ ] **Step 4: Test locally**

```bash
cd mcp-servers/zabbix
ZABBIX_API_URL=http://10.10.1.142/api_jsonrpc.php ZABBIX_API_TOKEN=<token> uv run mcp-zabbix
```

- [ ] **Step 5: Commit**

```bash
git add mcp-servers/zabbix/
git commit -m "feat: add Zabbix MCP server with pyzabbix"
```

---

### Task 4: Wire Zabbix MCP into OpenFang

**Files:**
- Modify: `openfang/config.toml`
- Modify: `Dockerfile.openfang`

- [ ] **Step 1: Pre-install Zabbix MCP deps in Dockerfile**

Add after the Juniper pre-install block:

```dockerfile
COPY mcp-servers/zabbix /tmp/mcp-zabbix
RUN cd /tmp/mcp-zabbix && uv sync && rm -rf /tmp/mcp-zabbix
```

- [ ] **Step 2: Add Zabbix MCP to config.toml**

```toml
[[mcp_servers]]
name = "zabbix"
timeout_secs = 30

[mcp_servers.transport]
type = "stdio"
command = "uvx"
args = ["--directory", "/usr/local/share/inframon/mcp-servers/zabbix", "mcp-zabbix"]
```

- [ ] **Step 3: Rebuild and verify**

```bash
docker compose -f docker-compose.openfang.yml up -d --build
```

Check logs for both MCP servers connecting:
```
MCP server connected  server=juniper  tools=9
MCP server connected  server=zabbix   tools=8
```

- [ ] **Step 4: Commit**

```bash
git add openfang/config.toml Dockerfile.openfang
git commit -m "feat: wire Zabbix MCP server into OpenFang"
```

---

## Chunk 3: Proxmox MCP Server

### Task 5: Create Proxmox MCP Server Package

**Files:**
- Create: `mcp-servers/proxmox/pyproject.toml`
- Create: `mcp-servers/proxmox/src/mcp_proxmox/__init__.py`
- Create: `mcp-servers/proxmox/src/mcp_proxmox/server.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "mcp-proxmox"
version = "0.1.0"
description = "Proxmox VE cluster MCP server for infrastructure monitoring"
requires-python = ">=3.10"
dependencies = [
    "fastmcp>=2.0",
    "proxmoxer>=2.0",
    "requests",
]

[project.scripts]
mcp-proxmox = "mcp_proxmox.server:main"
```

- [ ] **Step 2: Create package init**

```python
# mcp-servers/proxmox/src/mcp_proxmox/__init__.py
```

- [ ] **Step 3: Write the MCP server**

```python
# mcp-servers/proxmox/src/mcp_proxmox/server.py
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

mcp = FastMCP(
    "Proxmox VE MCP Server",
    description="Query Proxmox VE cluster for node status, VMs, storage, and cluster health.",
)


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
```

- [ ] **Step 4: Test locally**

```bash
cd mcp-servers/proxmox
PVE_API_URL=https://10.10.1.14:8006 PVE_API_TOKEN_ID=inframon@pam\!monitoring PVE_API_TOKEN_SECRET=<secret> uv run mcp-proxmox
```

- [ ] **Step 5: Commit**

```bash
git add mcp-servers/proxmox/
git commit -m "feat: add Proxmox MCP server with proxmoxer"
```

---

### Task 6: Wire Proxmox MCP into OpenFang

**Files:**
- Modify: `openfang/config.toml`
- Modify: `Dockerfile.openfang`

- [ ] **Step 1: Pre-install Proxmox MCP deps in Dockerfile**

Add after the Zabbix pre-install block:

```dockerfile
COPY mcp-servers/proxmox /tmp/mcp-proxmox
RUN cd /tmp/mcp-proxmox && uv sync && rm -rf /tmp/mcp-proxmox
```

- [ ] **Step 2: Add Proxmox MCP to config.toml**

```toml
[[mcp_servers]]
name = "proxmox"
timeout_secs = 30

[mcp_servers.transport]
type = "stdio"
command = "uvx"
args = ["--directory", "/usr/local/share/inframon/mcp-servers/proxmox", "mcp-proxmox"]
```

- [ ] **Step 3: Rebuild and verify**

```bash
docker compose -f docker-compose.openfang.yml up -d --build
```

Check logs for all three MCP servers:
```
MCP server connected  server=juniper  tools=9
MCP server connected  server=zabbix   tools=8
MCP server connected  server=proxmox  tools=7
```

- [ ] **Step 4: Commit**

```bash
git add openfang/config.toml Dockerfile.openfang
git commit -m "feat: wire Proxmox MCP server into OpenFang"
```

---

## Chunk 4: Slim Down Agent System Prompt

### Task 7: Update Agent System Prompt

**Files:**
- Modify: `openfang/agents/inframon/agent.toml`

Now that the agent discovers tools automatically via MCP, the system prompt no longer needs tool documentation. It should keep:
- Investigation protocol (when/how to investigate)
- Host inventory (hostids, IPs, names)
- Severity levels and notification rules
- Suppression rules
- VLAN reference

And remove:
- All tool usage documentation (Zabbix API examples, Proxmox API examples, Juniper API examples)
- Shell sandbox rules (agent no longer needs shell_exec for API queries)
- SSH section (proxmox-api.py SSH fallback replaced by MCP)

- [ ] **Step 1: Rewrite the Tools section**

Replace the entire `## Tools (Priority Order)` section (from `### 1. Zabbix API` through `### 4. SSH`) with:

```
## Tools

Your tools are provided automatically via MCP servers. Use the tool that matches your need:

**Zabbix MCP** — Monitoring data, alerts, and history
- get_active_problems, get_unacknowledged_problems — Current alerts
- get_hosts, get_host_items, get_history — Host metrics and trends
- get_triggers — Alert conditions for a host
- get_problem_details — Full context for a specific event_id
- acknowledge_event — Mark a problem as investigated

**Juniper MCP** — Real-time switch state (use for active investigation)
- get_interfaces, get_alarms, get_lldp_neighbors — Port and connectivity status
- get_environment, get_chassis_inventory — Hardware health
- get_mac_table — Trace device locations
- get_vlans, get_route_summary — Network configuration

**Proxmox MCP** — Hypervisor cluster status
- get_cluster_status, get_nodes, get_node_status — Cluster health
- get_vms — VM/container inventory and status
- get_storage, get_node_disks — Storage health

**When to use which:**
- Webhook alert arrives → get_problem_details (Zabbix) for context
- Network device issue → Juniper MCP for real-time + Zabbix for history
- Proxmox host issue → Proxmox MCP for node status + Zabbix for history
- After investigation → acknowledge_event (Zabbix) to mark as handled

**Knowledge Store (ak CLI) and Email Notifications (infra-notify)** are still available via shell_exec.
```

- [ ] **Step 2: Remove shell sandbox rules**

Remove the entire `## CRITICAL: Shell Sandbox Rules` section. The agent still has shell_exec for `ak` and `infra-notify`, but the sandbox rules about metacharacters are no longer critical since API queries go through MCP.

Replace with a minimal note:

```
## Shell Access

Shell commands are available for `ak` (knowledge store) and `infra-notify` (email notifications). API queries go through MCP tools — do not use shell_exec for API calls.
```

- [ ] **Step 3: Update Investigation Flow**

Replace the investigation flow diagram to reference MCP tools:

```
## Investigation Flow

```
Webhook Alert Received (host, severity, event_id, trigger_name, last_value)
    |
    v
Check suppression rules → if suppressed, log via ak store + stop
    |
    v
Query Zabbix MCP: get_problem_details(event_id), get_host_items(host)
    |
    v
Investigate with MCP tools:
  - Proxmox host → get_node_status, get_cluster_status, get_vms
  - Network switch → get_interfaces, get_alarms, get_lldp_neighbors
  - Historical context → get_history (Zabbix)
    |
    v
Synthesize: root cause, severity, recommendation
    |
    v
Notify (sev >= 3) via infra-notify or log-only (sev <= 2) via ak store
    |
    v
Acknowledge: acknowledge_event(event_id, findings)
```
```

- [ ] **Step 4: Update Alert Investigation Protocol Step 3**

Change Step 3 from:
```
**Step 3 — Investigate with appropriate tool:**
- Proxmox host → use Proxmox REST API (node status, cluster health)
- Network device → use Juniper REST API for real-time state + Zabbix for historical SNMP data
- Storage → use Proxmox API + zpool commands
```

To:
```
**Step 3 — Investigate with MCP tools:**
- Proxmox host → get_node_status, get_cluster_status, get_vms (Proxmox MCP)
- Network device → get_interfaces, get_alarms, get_lldp_neighbors (Juniper MCP) + get_history (Zabbix MCP)
- Any host → get_host_items for current metrics, get_history for trends (Zabbix MCP)
```

- [ ] **Step 5: Commit**

```bash
git add openfang/agents/inframon/agent.toml
git commit -m "feat: slim agent prompt — tools now auto-discovered via MCP"
```

---

### Task 8: Remove fetch PoC MCP Server

**Files:**
- Modify: `openfang/config.toml`

- [ ] **Step 1: Remove the fetch MCP entry**

Remove the `[[mcp_servers]]` block with `name = "fetch"` from config.toml. It was a PoC — the real servers replace it.

- [ ] **Step 2: Commit**

```bash
git add openfang/config.toml
git commit -m "chore: remove fetch MCP PoC — replaced by real servers"
```

---

## Chunk 5: End-to-End Validation

### Task 9: Rebuild and Test Full Pipeline

- [ ] **Step 1: Rebuild container**

```bash
docker compose -f docker-compose.openfang.yml up -d --build
```

- [ ] **Step 2: Verify all MCP servers connect**

```bash
docker logs bmic-inframon-openfang 2>&1 | grep "MCP"
```

Expected:
```
MCP server connected  server=juniper  tools=9
MCP server connected  server=zabbix   tools=8
MCP server connected  server=proxmox  tools=7
MCP: 24 tools available from 3 server(s)
```

- [ ] **Step 3: Test Juniper MCP via agent**

Open http://localhost:4200 and ask:
> "What are the current alarms on the ex3400 switch?"

Verify: Agent uses `get_alarms` MCP tool, returns JSON result.

- [ ] **Step 4: Test Zabbix MCP via agent**

Ask:
> "Show me all active problems in Zabbix"

Verify: Agent uses `get_active_problems` MCP tool.

- [ ] **Step 5: Test Proxmox MCP via agent**

Ask:
> "What's the cluster status?"

Verify: Agent uses `get_cluster_status` MCP tool.

- [ ] **Step 6: Test investigation flow**

Ask:
> "An interface went down on ex3400. Investigate and tell me what you find."

Verify the agent:
1. Queries Zabbix for related problems
2. Queries Juniper for real-time interface state
3. Cross-references both sources
4. Summarizes findings

- [ ] **Step 7: Final commit and push**

```bash
git push origin main
```

---

## Verification

| Check | Expected |
|-------|----------|
| `docker logs ... \| grep MCP` shows 3 servers, ~24 tools | All MCP servers connected |
| Agent uses `get_alarms` when asked about switch alarms | Juniper MCP working |
| Agent uses `get_active_problems` for Zabbix queries | Zabbix MCP working |
| Agent uses `get_cluster_status` for Proxmox queries | Proxmox MCP working |
| Agent system prompt is ~120 lines (down from ~250) | Prompt slimmed successfully |
| Agent still uses `ak store` and `infra-notify` via shell_exec | Non-MCP tools still work |

## Risks

1. **PyEZ NETCONF vs REST API** — We're switching from HTTP REST (port 3000) to NETCONF (port 830). Both switches have NETCONF enabled (`set system services netconf ssh`), but test connectivity from the container.
2. **uv cache cold start** — First `uvx` invocation downloads packages. The Dockerfile pre-install mitigates this, but if the cache is invalidated, startup will be slow (~30s). If this is an issue, consider `uv pip install` instead of `uvx`.
3. **pyzabbix auth** — pyzabbix uses `login(api_token=token)` for Zabbix 7.0 token auth. Verify this works (older pyzabbix versions may not support token auth — we need >=1.3).
4. **proxmoxer token format** — The `PVE_API_TOKEN_ID` contains `!` which is `user@realm!tokenname`. The `_get_api()` function splits on `!` to extract user and token_name — verify this works with the actual token.
5. **LLM tool selection** — With 24+ tools available, the Qwen model needs to pick the right one. The tool descriptions are the guidance now (not the system prompt). If tool selection is poor, we may need to add hints to the system prompt.
