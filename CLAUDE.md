# inframon

OpenFang-based infrastructure monitoring agent for BMIC. Monitors Proxmox cluster, Juniper switches, Zabbix alerts, and PBS backup servers via Matrix/webhook interface.

## OpenFang Reference

For comprehensive OpenFang platform docs, read `openfang/docs/SUMMARY.md` — it covers agents, skills, hands, channels, API, CLI, workflows, and troubleshooting in a single pass. Full upstream docs are in `openfang/docs/`.

## Architecture

- **Runtime:** OpenFang agent OS in Docker (`docker-compose.openfang.yml`)
- **Agents:** Three specialized agents — `inframon` (interactive chat), `inframon-triage` (webhook alert handling), `inframon-patrol` (nightly health sweeps)
- **LLM:** Qwen 3.5 35B via OpenRouter (fallback: Gemini 2.5 Flash)
- **Interface:** Matrix bot (@inframon:matrix.org) + webhook gateway (port 8460)
- **Skills:** `skills/` directory — Agent Skills standard (SKILL.md + scripts), stdlib-only Python
- **MCP Servers:** `mcp-servers/` directory — legacy, no longer built or used (kept for reference)

## Key Files

| File | Purpose |
|------|---------|
| `openfang/config.toml` | OpenFang config: channels, model, approval |
| `openfang/agents/inframon/agent.toml` | Agent system prompt, capabilities, model config |
| `docker-compose.openfang.yml` | Container config, env vars, volumes, networking |
| `Dockerfile.openfang` | Container build (no third-party deps) |
| `skills/` | Agent Skills (juniper, zabbix, proxmox, pbs monitoring) |
| `openfang/agents/inframon-triage/agent.toml` | Triage agent: webhook alert investigation |
| `openfang/agents/inframon-patrol/agent.toml` | Patrol agent: nightly proactive health sweeps |
| `skills/matrix-notify/` | Room-targeted Matrix messaging skill |

## Skill Pattern

All monitoring skills follow the same structure:
```
skills/<name>/
├── SKILL.md              # Metadata (name, description, trigger words), docs, investigation patterns
└── scripts/
    └── <name>_query.py   # argparse CLI, JSON output, stdlib only
```

**Env var recovery** — OpenFang strips env vars from shell_exec subprocesses. Every skill script reads `/proc/1/environ` at import time:
```python
_proc_env = Path("/proc/1/environ")
if _proc_env.exists():
    for entry in _proc_env.read_bytes().split(b"\0"):
        if b"=" in entry:
            k, v = entry.decode("utf-8", errors="replace").split("=", 1)
            os.environ.setdefault(k, v)
```

## Known Gotchas

- **OpenFang strips env vars** — shell_exec subprocesses; recover from `/proc/1/environ`
- **OpenFang approval** — needs BOTH `require_approval=false` AND `auto_approve=true`
- **Shell sandbox blocks curly braces** — use Python wrapper scripts instead of inline shell
- **Juniper REST API** — port 3000, returns multipart XML (scripts handle conversion to JSON)

## Infrastructure

### Proxmox Cluster
pve-r720 (10.10.1.14), pve-p520 (10.10.1.80), pve-z2 (10.10.1.77), pve5820gpu (10.10.1.92)

### PBS Instances
primary (10.10.1.141), ts140 (10.10.1.145), offsite (100.100.58.6)

### Switches
bmic-ex3400-1 (10.10.1.10), bmic-ex2300-1 (10.10.1.9), bmic-icx6610-1 (10.10.1.254)

### TrueNAS
truenas-ts140 (10.10.1.78) — TrueNAS SCALE 25.04, pool: tank (mirror)

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
- `JUNIPER_USER`, `JUNIPER_PASSWORD` — Switch REST API
- `MATRIX_ACCESS_TOKEN` — Matrix bot
- `WEBHOOK_SECRET` — Zabbix webhook auth
- `PBS_INSTANCES`, `PBS_API_TOKEN_ID`, `PBS_API_TOKEN_SECRET` — PBS monitoring
- `TRUENAS_URL`, `TRUENAS_API_KEY` — TrueNAS SCALE monitoring
