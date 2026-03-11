# Inframon

AI-powered infrastructure monitoring and troubleshooting service for BMIC's Zabbix + Proxmox environment.

## Overview

**Inframon** is an autonomous agent that monitors Zabbix alerts and provides a web-based chat interface for human-in-the-loop troubleshooting. When an infrastructure problem occurs, operators can:

1. Click a link in Slack/email to open the web UI with alert context pre-populated
2. Chat with the **inframon** agent to investigate the problem
3. Review findings and approve remediation steps
4. Maintain a persistent history of all investigations

## Architecture

```
┌─────────────────────────────────────────────┐
│  Zabbix Alert Detection                     │
│  (unacknowledged problems)                  │
└────────────────┬────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────┐
│  inframon Agent (pi-based)                  │
│  - Polls Zabbix every 5 minutes             │
│  - Generates alert notifications            │
│  - Provides investigation via skills        │
└────────────────┬────────────────────────────┘
                 │
         ┌───────┴────────┐
         ↓                ↓
    Slack/Email      Web UI (ChatPanel)
    (Notification)   (Human Investigation)
         │                │
         └────────┬───────┘
                  ↓
         ┌──────────────────────┐
         │ IndexedDB Storage    │
         │ (Session Persistence)│
         └──────────────────────┘
```

## Quick Start

### Prerequisites

- Docker + Docker Compose
- Zabbix API token (from `~/.config/infra-monitor/.env` or bmic-proxmox)
- Proxmox API token

### Setup

```bash
# Clone and navigate
cd ~/git/inframon

# Copy environment template
cp .env.example .env

# Edit with your credentials
# - ZABBIX_API_TOKEN
# - PROXMOX credentials
# - Optional: PI_MODEL (default: claude-opus-4-6)
nano .env

# Build and run
docker-compose build
docker-compose up -d

# View logs
docker-compose logs -f inframon
```

The web UI will be available at `http://localhost:3000`

### Local Development

```bash
# Install dependencies
npm install
cd web-ui-app && npm install && cd ..

# Run agent + web-ui (requires pi installed globally)
npm run dev

# Or run web-ui only
cd web-ui-app && npm run dev
```

## Usage

### Web UI

Navigate to `http://localhost:3000` and start a chat session.

#### Alert Context URL

Share alert-specific investigation links:

```
http://localhost:3000?alert_id=12345&host=ex3400&problem=interface-down
```

Parameters:
- `alert_id` - Zabbix alert/problem ID
- `host` - Affected host
- `problem` - Problem description

### Agent Skills

**inframon** has access to three skills:

#### zabbix-ops
Query Zabbix API for alert details, history, and trends:
- `query-problems` - Get unacknowledged problems
- `get-history` - Historical metric data
- `acknowledge-problem` - Mark problem as resolved

#### proxmox-admin
Check Proxmox cluster and host status:
- `get-cluster-status` - Overall cluster health
- `get-node-status` - CPU, memory, disk usage
- `get-storage-status` - Storage pool utilization
- `list-vms` - VM status and resources

#### junos-config
Query Juniper switches:
- `get-interface-status` - Port status and errors
- `get-bgp-status` - BGP session status
- `get-route-table` - Routing information
- `get-configuration` - Switch config

## Configuration

### `.pi/agent/agents/inframon.md`

Agent definition with system prompt, skills, and model configuration.

### `.pi/agent/models.json`

Model provider configuration (in `~/.pi/agent/models.json`):

```json
{
  "providers": {
    "anthropic": {
      "apiKey": "sk-ant-..."
    }
  }
}
```

## Deployment

### Docker

```bash
docker build -t inframon:latest .
docker run -p 3000:3000 \
  -e ZABBIX_API_TOKEN="your-token" \
  -e PROXMOX_HOST="pve-r720" \
  -v ./logs:/app/logs \
  inframon:latest
```

### Docker Compose

```bash
docker-compose up -d
```

### Proxmox (LXC Container)

1. Create Ubuntu 22.04 LXC container
2. Install Docker and Docker Compose
3. Clone inframon repo
4. Run `docker-compose up -d`

## Development

### Project Structure

```
inframon/
├── .pi/
│   └── agent/
│       ├── agents/
│       │   └── inframon.md          # Agent definition
│       └── skills/
│           ├── zabbix-ops.md
│           ├── proxmox-admin.md
│           └── junos-config.md
├── web-ui-app/
│   ├── src/
│   │   ├── main.ts                  # ChatPanel entry point
│   │   └── app.css
│   ├── index.html
│   ├── vite.config.ts
│   └── package.json
├── src/                             # Agent daemon code (future)
├── Dockerfile
├── docker-compose.yml
├── pm2.config.js
└── README.md
```

### Adding Custom Skills

Create a new skill file in `.pi/agent/skills/`:

```markdown
# my-skill

Description of what the skill does.

## Tools

### tool-name
Description.

**Parameters:**
- `param1` - Description

**Returns:** What it returns
```

Then reference it in `.pi/agent/agents/inframon.md`:

```yaml
skills:
  - zabbix-ops
  - proxmox-admin
  - my-skill
```

## Troubleshooting

### Web UI not loading

```bash
docker-compose logs inframon
```

Check:
- Port 3000 is not in use
- Network connectivity to Zabbix/Proxmox

### Agent not processing alerts

```bash
docker-compose exec inframon pm2 logs inframon-agent
```

Check:
- Zabbix API token is valid
- Agent can reach Zabbix API URL
- No unacknowledged problems in Zabbix (create test alert)

### Model errors

If Claude API key is missing:
1. Click Settings (⚙️) in web UI
2. Click "Manage API Keys"
3. Add your Anthropic API key

## Related Documentation

- **bmic-proxmox** — Infrastructure setup (Zabbix, Proxmox, networking)
- **pi-mono** — Agent framework documentation
- **Zabbix API** — Official API reference

## License

Internal BMIC project.
