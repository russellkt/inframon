# Setup Guide

## Prerequisites

1. **Zabbix Server** running and accessible
   - API endpoint: `http://zabbix:8080/api_jsonrpc.php`
   - Admin user with API access

2. **Proxmox Cluster** (optional, for VM/node investigation)
   - API user token
   - Network access to cluster

3. **Docker + Docker Compose** (for containerized deployment)

4. **Anthropic API Key** (for Claude)
   - Get from https://console.anthropic.com/

## Configuration

### Step 1: Get Zabbix API Token

From **bmic-proxmox**:
```bash
# The token is stored in ~/.config/infra-monitor/.env
cat ~/.config/infra-monitor/.env | grep ZABBIX_API_TOKEN
```

Or generate new:
1. Log into Zabbix web UI
2. User Settings → API Tokens
3. Create token for `zabbix@pam` user
4. Copy token value

### Step 2: Get Proxmox API Token

From Proxmox host:
```bash
# As root on pve-r720
pveum user add inframon@pam
pveum acl grant / -user inframon@pam -role Administrator
pveum token add inframon@pam inframon-token
# Copy the token value
```

### Step 3: Configure Inframon

```bash
cd ~/git/inframon
cp .env.example .env

# Edit with your values
cat .env
```

Required values:
```env
ZABBIX_API_TOKEN=pve1234567890abcdef...
PROXMOX_HOST=pve-r720.bmic.local
PROXMOX_USER=root@pam
PROXMOX_TOKEN_ID=inframon-token
PROXMOX_TOKEN_SECRET=your-token-secret...
```

### Step 4: Configure Models (Optional)

For local inference (faster, cheaper):

**Option A: Use Claude (default)**
```bash
# Requires ANTHROPIC_API_KEY in environment or web UI
# No setup needed
```

**Option B: Local models via OpenRouter**

Edit `~/.pi/agent/models.json`:
```json
{
  "providers": {
    "openrouter": {
      "apiKey": "sk-or-v1-...",
      "baseUrl": "https://openrouter.ai/api/v1"
    }
  },
  "models": {
    "qwen": {
      "name": "qwen/qwen3-coder-30b-a3b-instruct",
      "provider": "openrouter"
    }
  }
}
```

Then edit `.pi/agent/agents/inframon.md`:
```yaml
model: qwen
```

**Option C: Local llama-server**

```bash
# On GPU box (RTX 4060 Ti)
ollama pull qwen3:7b
llama-server --model qwen3:7b --port 8000
```

Edit `~/.pi/agent/models.json`:
```json
{
  "providers": {
    "openai": {
      "apiKey": "not-used",
      "baseUrl": "http://localhost:8000/v1"
    }
  }
}
```

## Deployment

### Docker Compose (Recommended)

```bash
cd ~/git/inframon
docker-compose build
docker-compose up -d

# Verify
docker-compose logs -f inframon
```

Access at: http://localhost:3000

### Local Development

```bash
cd ~/git/inframon

# Install pi globally first
npm install -g @mariozechner/pi

# Install dependencies
npm install
cd web-ui-app && npm install && cd ..

# Run agent + web UI
npm run dev
```

## Verification

### Test Zabbix Connection

```bash
curl -X POST http://zabbix:8080/api_jsonrpc.php \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "apiinfo.version",
    "params": [],
    "id": 1
  }'
```

Should return Zabbix version.

### Test Agent

```bash
# In web UI
Type: "Show me unacknowledged Zabbix problems"

# Agent should query Zabbix and return list
```

### Check Logs

```bash
# Docker
docker-compose logs inframon

# Development
tail -f logs/*.log
```

## Troubleshooting

**Web UI doesn't load:**
- Check port 3000: `lsof -i :3000`
- Check logs: `docker-compose logs web-ui`

**Agent can't reach Zabbix:**
- Verify `ZABBIX_API_URL` and `ZABBIX_API_TOKEN`
- Check firewall: `ping zabbix` from container

**Model errors:**
- Add API key via web UI Settings
- Or set `ANTHROPIC_API_KEY` environment variable

## Next Steps

1. **Create test alert** in Zabbix to verify agent can detect problems
2. **Test remediation** with agent approval workflow
3. **Set up notifications** to include web UI link
4. **Monitor logs** for issues

See [ARCHITECTURE.md](./ARCHITECTURE.md) for design details.
