# Architecture

## System Design

```
┌─────────────────────────────────────────────────────────┐
│                     Zabbix Server                       │
│   - Collects metrics from hosts                        │
│   - Detects problems via triggers                      │
│   - Exposes JSON-RPC API                              │
└────────┬───────────────────────────────────────────────┘
         │ (problem.get)
         │
    ┌────┴──────────────────────────────────────────────────┐
    │         EXTERNAL POLLING (macOS launchd)               │
    │  ~/git/bmic-proxmox/scripts/infra-monitor/            │
    │     poll_zabbix.py (runs every 5 minutes)             │
    │     - Queries unacknowledged problems                  │
    │     - Generates Investigate URLs                       │
    │     - Sends notifications with links                   │
    └────┬──────────────────────────────────────────────────┘
         │
         └──────────────┬──────────────────┐
                        ↓                  ↓
                   ┌─────────┐       ┌───────────┐
                   │  Slack  │       │  Email    │
                   │  notify │       │  notify   │
                   └────┬────┘       └─────┬─────┘
                        │                  │
                        └─────────┬────────┘
                                  │
         (Click Investigate link)  │
                                  ↓
    http://localhost:3000?alert_id=123&host=ex3400
                                  │
                        ┌─────────┴────────────┐
                        ↓                      ↓
    ┌─────────────────────────────┐  ┌──────────────────────┐
    │  Web UI Container (Docker)  │  │ Express API Proxy    │
    │                             │  │ (localhost:3001)     │
    │  - ChatPanel (pi-web-ui)    │  │                      │
    │  - Custom tools:            │  │ Routes:              │
    │    * zabbixTool             │  │  POST /api/zabbix    │
    │    * proxmoxTool            │  │  GET  /api/proxmox   │
    │  - Session storage (IDB)    │  │  GET  /health        │
    │  - Model configuration      │  │                      │
    └──────────┬──────────────────┘  └──────────┬───────────┘
               │                                 │
               └────────────┬────────────────────┘
                            │
                  ┌─────────┴──────────┐
                  ↓                    ↓
             ┌──────────┐        ┌──────────┐
             │ Zabbix   │        │ Proxmox  │
             │ API      │        │ Cluster  │
             │ (10.x)   │        │ (SSH)    │
             └──────────┘        └──────────┘
```

## Components

### 1. Polling System (External - macOS)

**File:** `~/git/bmic-proxmox/scripts/infra-monitor/poll_zabbix.py`

**Process:**
1. Runs every 5 minutes via launchd (launchctl)
2. Connects to Zabbix API at `10.10.1.142/api_jsonrpc.php`
3. Queries `problem.get` for unacknowledged alerts
4. For each alert:
   - Constructs `Investigate` URL with alert context:
     ```
     http://localhost:3000?alert_id=<eventid>&host=<hostname>&problem=<trigger>
     ```
   - Sends notification (Slack/email) containing the URL
5. Acknowledges in Zabbix with `[inframon]` prefix
6. Stores findings in ak (agent-knowledge) for persistence

**Configuration:**
- `.env` file at `~/.config/infra-monitor/.env`
- Required vars: `ZABBIX_API_URL`, `ZABBIX_API_TOKEN`, `INFRAMON_WEB_URL`

**Dependencies:**
- `zabbix-utils` (Python library)
- SSH access to Proxmox for diagnostics
- Email/Slack webhook for notifications

### 2. Express API Proxy (Docker)

**File:** `src/server.ts`

**Purpose:** Bridge between web UI and backend APIs (Zabbix, Proxmox)

**Endpoints:**
- `GET /health` — Health check
- `POST /api/zabbix` — Proxy JSON-RPC calls to Zabbix
- `GET /api/proxmox/nodes` — SSH to pve-r720, run `pvesh get /nodes`

**Environment:**
- `PORT_API=3001` (default)
- `ZABBIX_API_URL` (e.g., `http://10.10.1.142/api_jsonrpc.php`)
- `ZABBIX_API_TOKEN`

**Features:**
- CORS-enabled for local development
- Bearer token injection for Zabbix
- SSH-based Proxmox access (no REST API token needed)
- Error handling with helpful hints

### 3. Web UI (Docker)

**Files:** `web-ui-app/src/`

**Technology:**
- Lit web components
- ChatPanel from `@mariozechner/pi-web-ui`
- Custom tools: `tools.ts`
- IndexedDB for session persistence
- Vite for bundling

**Custom Tools:**
```typescript
zabbixTool  // POST /api/zabbix with JSON-RPC body
proxmoxTool // GET  /api/proxmox/nodes
```

**Features:**
- Pre-populated alert context from URL params
- Alert banner in header showing active problem
- Session history (Clock button)
- Model/API key configuration via Settings
- Theme toggle

**Entry Points:**
- `/` — New session
- `/?session=uuid` — Resume session
- `/?alert_id=123&host=ex3400&problem=High+CPU` — Pre-populated investigation

### 4. Inframon Agent Definition

**File:** `.pi/agent/agents/inframon.md`

**Model:** `openrouter/google/gemini-2.5-flash`

**Skills (symlinked from `~/.pi/agent/skills/`):**
- `zabbix-ops` — Query Zabbix API via skill
- `proxmox-admin` — Check Proxmox status
- `junos-config` — Query Juniper switches
- `notify` — Route findings to channels
- `ak-infra` — Store in knowledge store

**Tools:** `read, grep, find, ls, bash`

## Data Flow

### Alert Detection to Web UI

```
1. poll_zabbix.py finds unacknowledged problem in Zabbix
2. Generates URL:
   http://localhost:3000?alert_id=15493911&host=pve-r720&problem=High+CPU
3. Sends email/Slack with "Investigate" link
4. Human clicks link → Web UI loads
5. ChatPanel pre-populates with:
   "Alert: pve-r720 — High CPU (ID: 15493911). Please investigate..."
```

### Investigation via Custom Tools

```
1. Human asks: "Show me the CPU status"
2. Web UI agent calls zabbixTool
   {
     "method": "history.get",
     "params": {"hostid": "10596", "key_": "system.cpu.load"}
   }
3. zabbixTool calls POST /api/zabbix (Express proxy)
4. Proxy injects Bearer token, calls Zabbix
5. Zabbix returns historical CPU data
6. Agent streams findings to chat
```

## Deployment

### Development

```
Terminal 1: npm run dev:server   # Express proxy on :3001
Terminal 2: cd web-ui-app && npm run dev  # Web UI on :3000

Configuration: .env in current directory
```

### Docker

```
docker-compose up -d

Services:
  - Web UI: http://localhost:3000
  - API Proxy: http://localhost:3001 (internal)
  - pm2 manages: inframon-api + inframon-web-ui

Polling: Still external via launchd (not in container)
```

### Production (Proxmox LXC)

```
1. Create Ubuntu 22.04 LXC container on pve-r720
2. Install Docker + docker-compose
3. Clone inframon repo, populate .env
4. docker-compose up -d
5. Polling via launchd continues on Mac (or move to container)
```

### Future: Tailscale Integration

See [TAILSCALE.md](./TAILSCALE.md) for securing access via Tailscale mesh VPN.

**Current code is already compatible** — just update `.env` with `*.tailscale.local` hostnames.

```env
ZABBIX_API_URL=http://zabbix.tailscale.local/api_jsonrpc.php
PROXMOX_HOST=proxmox.tailscale.local
INFRAMON_WEB_URL=https://inframon.tailscale.local
```

## Files Reference

| Path | Purpose |
|------|---------|
| `pm2.config.js` | Process manager: inframon-api, inframon-web-ui |
| `src/server.ts` | Express proxy server |
| `web-ui-app/src/tools.ts` | Custom ChatPanel tools |
| `web-ui-app/src/main.ts` | Web UI entry point + alert pre-population |
| `.pi/agent/agents/inframon.md` | Agent definition + system prompt |
| `.pi/agent/skills/` | Symlinks to ~/.pi/agent/skills/ |
| `.env.example` | Environment template |
| `docker-compose.yml` | Service definitions |
| `Dockerfile` | Container image |
| `~/git/bmic-proxmox/scripts/infra-monitor/poll_zabbix.py` | External poller |

## Security

### API Tokens

- **Zabbix token:** In `.env` (mounted volume in Docker)
- **OpenRouter API key:** In web UI Settings (IndexedDB, never sent to backend)
- **Proxmox:** SSH key-based (no REST token needed)

### Network Access

- **Web UI ↔ API Proxy:** localhost (Docker internal)
- **Docker Network:** 10.10.100.0/24 (tagged for infrastructure LAN access)
- **API Proxy ↔ Zabbix:** 10.10.100.x → 10.10.1.142 (internal network)
- **API Proxy ↔ Proxmox:** 10.10.100.x → 10.10.1.x (SSH on internal network)
- **Polling ↔ Zabbix:** External via launchd on macOS (10.10.1.142)
- **Web UI ↔ AI Provider:** Direct from browser (user's API key)

## Error Handling

**Polling Failures:**
- Zabbix unreachable → log + retry next cycle
- SSH diagnostics fail → note in triage
- Notification fails → log to file

**Web UI Failures:**
- API proxy down → show error in chat
- Zabbix API returns error → forward error message
- Session save fails → warn user

See [SETUP.md](./SETUP.md) for configuration and troubleshooting.
