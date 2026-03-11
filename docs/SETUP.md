# Setup Guide

## Overview

Inframon has two components:

1. **Polling System (External):** Runs on macOS via launchd, queries Zabbix every 5 minutes
2. **Web UI + API Proxy (Docker):** Serves the investigation interface and proxies API calls

## Prerequisites

### Polling System (macOS)

- Python 3.8+
- `zabbix-utils` library
- SSH access to Proxmox cluster
- Network access to Zabbix API (10.10.1.142)

### Web UI + API Proxy (Docker)

- Docker + Docker Compose
- Ports 3000 (web UI) and 3001 (API proxy) available
- Network access to Zabbix API and Proxmox cluster

### AI Provider

- **Claude (Anthropic):** Enter API key in web UI Settings
- **OpenRouter:** Set `OPENROUTER_API_KEY` in Docker .env
- **Local:** Already configured to use local llama-server on RTX 4060 Ti

## Configuration

### Step 1: Polling System Environment (.env for poll_zabbix.py)

Location: `~/.config/infra-monitor/.env`

```bash
mkdir -p ~/.config/infra-monitor

cat > ~/.config/infra-monitor/.env << 'EOF'
# Zabbix API configuration
ZABBIX_API_URL=http://10.10.1.142/api_jsonrpc.php
ZABBIX_API_TOKEN=<your-zabbix-api-token>

# Notification webhook (optional)
NOTIFY_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK
NOTIFY_WEBHOOK_API_KEY=<optional>

# Inframon Web URL (for notification links)
INFRAMON_WEB_URL=http://localhost:3000
EOF
```

### Get Zabbix API Token

```bash
# Token already exists in the config, or generate new:
# 1. Log into Zabbix web UI (10.10.1.142)
# 2. User Settings → API Tokens
# 3. Create token for `zabbix@pam` user
# 4. Copy token value to .env
```

### Step 2: Docker Environment (.env for Docker Compose)

Location: `~/git/inframon/.env`

```bash
cd ~/git/inframon
cp .env.example .env
```

Edit `.env` with:

```env
# Zabbix API (same as polling system)
ZABBIX_API_URL=http://10.10.1.142/api_jsonrpc.php
ZABBIX_API_TOKEN=<your-zabbix-api-token>

# LLM configuration (if using OpenRouter)
OPENROUTER_API_KEY=sk-or-v1-<your-key>

# Port configuration
PORT=3000
PORT_API=3001
NODE_ENV=production
```

### Step 3: Verify Zabbix Connection

```bash
# Test from local machine
curl -X POST http://10.10.1.142/api_jsonrpc.php \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your-token>" \
  -d '{
    "jsonrpc": "2.0",
    "method": "apiinfo.version",
    "params": [],
    "id": 1
  }'

# Should return: {"jsonrpc":"2.0","result":"6.0.X","id":1}
```

## Deployment

### Option A: Docker Compose (Recommended)

```bash
cd ~/git/inframon

# Build and start
docker-compose build
docker-compose up -d

# Verify services
docker-compose logs -f

# Access web UI
open http://localhost:3000
```

Verify both services are running:
```bash
docker-compose ps
# Should show: inframon-api and inframon-web-ui

# Check API health
curl http://localhost:3001/health
# Should return: {"status":"ok"}
```

### Option B: Local Development

```bash
cd ~/git/inframon

# Install dependencies
npm install
cd web-ui-app && npm install --legacy-peer-deps && cd ..

# Terminal 1: Start Express API server
npm run dev:server
# Listens on http://localhost:3001

# Terminal 2: Start Web UI (in another terminal)
cd web-ui-app
npm run dev
# Listens on http://localhost:3000 (with hot reload)
```

### Option C: Production (Proxmox LXC)

```bash
# On pve-r720, create Ubuntu 22.04 LXC container
# Then inside container:

apt-get update && apt-get install -y docker.io docker-compose
cd /opt && git clone https://github.com/your-org/inframon.git
cd inframon

# Copy .env (securely)
scp .env container:/opt/inframon/

# Start
docker-compose up -d
```

## Polling System Setup

The polling system runs externally on macOS via launchd.

### Step 1: Verify Script

```bash
cd ~/git/bmic-proxmox/scripts/infra-monitor

# Test with --dry-run (doesn't acknowledge or notify)
python3 poll_zabbix.py --dry-run

# Check output
tail ~/.config/infra-monitor/poll.log
```

Sample output:
```
2026-03-11 12:30:45 INFO eventid=15493911 host=pve-r720 disposition=actionable
2026-03-11 12:30:45 INFO [DRY RUN] Would acknowledge eventid=15493911
2026-03-11 12:30:45 INFO [DRY RUN] Would send 1 email for 1 actionable alert(s)
```

### Step 2: Verify Investigate URL

Check the notification body in the logs:

```bash
grep -A 5 "Investigate:" ~/.config/infra-monitor/poll.log

# Should show:
# Investigate: http://localhost:3000?alert_id=15493911&host=pve-r720&problem=High+CPU+usage
```

### Step 3: LaunchD Configuration

Already configured at `~/Library/LaunchAgents/com.bmic.infra-alert-poll.plist`

Verify it's running:
```bash
launchctl list | grep infra-alert-poll
# Should show: -	0	com.bmic.infra-alert-poll  (exit code 0 = healthy)
```

To reload after changes:
```bash
launchctl unload ~/Library/LaunchAgents/com.bmic.infra-alert-poll.plist
launchctl load ~/Library/LaunchAgents/com.bmic.infra-alert-poll.plist
```

## Web UI Configuration

### First Time Setup

1. Open http://localhost:3000
2. Click Settings ⚙️
3. Select AI Provider:
   - **Claude (Anthropic):** Enter API key from https://console.anthropic.com
   - **OpenRouter:** Uses env var `OPENROUTER_API_KEY`
   - **Other:** Select from available options

### Using with Alert Link

1. Click an "Investigate" link from notification
2. Web UI automatically pre-populates:
   - Alert banner at top with host and problem
   - Chat message with alert context
3. Agent starts investigation immediately

Example URL:
```
http://localhost:3000?alert_id=15493911&host=pve-r720&problem=High+CPU
```

### Session History

- Click Clock button to view past investigations
- Sessions stored in browser IndexedDB
- Resumable across browser restarts

## Verification Checklist

- [ ] Zabbix API connection works
- [ ] Docker services running (`docker-compose ps`)
- [ ] Web UI accessible at http://localhost:3000
- [ ] API proxy health check: `curl http://localhost:3001/health`
- [ ] LaunchD polling agent running: `launchctl list | grep infra-alert-poll`
- [ ] Test alert received in Zabbix
- [ ] Notification with Investigate link sent
- [ ] Web UI opens and pre-populates with alert context
- [ ] Agent can query Zabbix via custom tool

## Troubleshooting

### Web UI doesn't load (Port 3000)

```bash
# Check if port is in use
lsof -i :3000

# Check logs
docker-compose logs inframon-web-ui

# Or if running locally
cd web-ui-app && npm run dev
```

### API proxy error (Port 3001)

```bash
# Check health endpoint
curl http://localhost:3001/health

# Check logs
docker-compose logs inframon-api

# Or if running locally
npm run dev:server
```

### Zabbix API connection failed

```bash
# Verify endpoint
curl http://10.10.1.142/api_jsonrpc.php

# Verify token in Docker
docker-compose exec inframon-api env | grep ZABBIX

# Check web UI logs for errors
docker-compose logs inframon-api | grep -i error
```

### Polling not running

```bash
# Check launchd status
launchctl list | grep infra-alert-poll

# Manual test
cd ~/git/bmic-proxmox/scripts/infra-monitor
python3 poll_zabbix.py --dry-run

# Check logs
tail ~/.config/infra-monitor/poll.log
```

### Agent can't query Zabbix from web UI

1. Verify API proxy is running: `curl http://localhost:3001/health`
2. Test proxy directly:
   ```bash
   curl -X POST http://localhost:3001/api/zabbix \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","method":"apiinfo.version","params":[],"id":1}'
   ```
3. Check proxy logs: `docker-compose logs inframon-api | grep -i error`

## Next Steps

1. **Create test alert** in Zabbix to verify end-to-end flow
2. **Test with real alert** from your infrastructure
3. **Configure notifications** in your Slack/email system
4. **Monitor logs** for issues: `tail -f ~/.config/infra-monitor/poll.log`

See [ARCHITECTURE.md](./ARCHITECTURE.md) for system design details.
