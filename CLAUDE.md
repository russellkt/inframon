# inframon

OpenFang-based infrastructure monitoring agent for BMIC. Monitors Proxmox cluster, Juniper switches, Zabbix alerts, and PBS backup servers via Telegram/webhook interface.

## Architecture

- **Runtime:** OpenFang agent OS in Docker (`docker-compose.openfang.yml`)
- **LLM:** Qwen 3.5 35B via OpenRouter (fallback: Gemini 2.5 Flash)
- **Interface:** Telegram bot (@Inframonbotbot) + webhook gateway (port 8460)
- **MCP Servers:** 3 stdio servers (juniper, zabbix, proxmox) — FastMCP 2.x, registered in `config.toml`
- **Skills:** `skills/` directory — Agent Skills standard (SKILL.md + scripts)

## Key Files

| File | Purpose |
|------|---------|
| `openfang/config.toml` | OpenFang config: MCP servers, channels, model, approval |
| `openfang/agents/inframon/agent.toml` | Agent system prompt, capabilities, model config |
| `docker-compose.openfang.yml` | Container config, env vars, volumes, networking |
| `Dockerfile.openfang` | Container build — installs MCP servers into /opt/mcp-venv |
| `mcp-servers/` | FastMCP 2.x MCP servers (juniper, zabbix, proxmox) |
| `skills/` | Agent Skills (pbs-monitoring) |
| `openfang/scripts/` | Shell-accessible scripts mounted at /usr/local/share/inframon/scripts |

## MCP Server Pattern

All MCP servers follow the same structure:
```
mcp-servers/<name>/
├── pyproject.toml          # hatchling build, fastmcp>=2.0,<3.0, entry point
└── src/mcp_<name>/
    ├── __init__.py
    └── server.py           # FastMCP('Name'), @mcp.tool(), main() calls mcp.run()
```

**Env var recovery** — OpenFang strips env vars from MCP subprocesses. Every server reads `/proc/1/environ` at import time:
```python
_proc_env = Path("/proc/1/environ")
if _proc_env.exists():
    for entry in _proc_env.read_bytes().split(b"\0"):
        if b"=" in entry:
            k, v = entry.decode("utf-8", errors="replace").split("=", 1)
            os.environ.setdefault(k, v)
```

## Known Gotchas

- **FastMCP pinned to 2.x** — 3.x stdio transport hangs on tool calls
- **FastMCP 3.x API change** — `FastMCP('Name')` only, no `description=` kwarg
- **OpenFang strips env vars** — both shell_exec and MCP subprocesses; recover from `/proc/1/environ`
- **uvx doesn't install local packages** — use `uv pip install` into a venv with entry points
- **OpenFang approval** — needs BOTH `require_approval=false` AND `auto_approve=true`
- **Shell sandbox blocks curly braces** — use Python wrapper scripts instead of inline shell

## Infrastructure

### Proxmox Cluster
pve-r720 (10.10.1.14), pve-p520 (10.10.1.80), pve-z2 (10.10.1.77), pve5820gpu (10.10.1.92)

### PBS Instances
primary (10.10.1.141), ts140 (10.10.1.145), offsite (100.100.58.6)

### Switches
bmic-ex3400-1 (10.10.1.10), bmic-ex2300-1 (10.10.1.9), bmic-icx6610-1 (10.10.1.254)

### Monitoring
Zabbix server at 127.0.0.1 (in-container), web UI at 10.10.1.77

## Deployment

```bash
docker compose -f docker-compose.openfang.yml up -d --build
docker compose -f docker-compose.openfang.yml logs -f
```

## Environment Variables

Set in `.env`, passed through `docker-compose.openfang.yml`:
- `OPENROUTER_API_KEY` — LLM access
- `ZABBIX_API_URL`, `ZABBIX_API_TOKEN` — Zabbix monitoring
- `PVE_API_URL`, `PVE_API_TOKEN_ID`, `PVE_API_TOKEN_SECRET` — Proxmox VE
- `JUNIPER_USER`, `JUNIPER_PASSWORD` — Switch NETCONF
- `TELEGRAM_BOT_TOKEN` — Telegram bot
- `WEBHOOK_SECRET` — Zabbix webhook auth
- `PBS_INSTANCES`, `PBS_API_TOKEN_ID`, `PBS_API_TOKEN_SECRET` — PBS monitoring
