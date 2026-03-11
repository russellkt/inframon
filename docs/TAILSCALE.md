# Tailscale Integration Plan

## Overview

Inframon will be deployed on Tailscale to secure access to internal infrastructure APIs (Zabbix, Proxmox, Juniper).

## Current Architecture

```
Internet
  └─ User Browser
      └─ http://localhost:3000 (local Docker)
          ├─ Express API Proxy (localhost:3001)
          │   ├─ POST /api/zabbix → http://10.10.1.142/api_jsonrpc.php
          │   └─ GET /api/proxmox → SSH pve-r720.bmic.local
          └─ ChatPanel Web UI (pi-web-ui)
```

**Limitation:** Assumes direct network access to 10.10.x.x (LAN only)

## Tailscale Topology

```
Internet
  └─ User Browser (Tailscale connected)
      └─ https://<inframon-node>.tailscale.local/
          ├─ Express API Proxy
          │   ├─ POST /api/zabbix → http://<zabbix-node>.tailscale.local/api_jsonrpc.php
          │   └─ GET /api/proxmox → SSH <proxmox-node>.tailscale.local
          └─ ChatPanel Web UI
```

**Benefits:**
- Secure: All traffic encrypted end-to-end via Tailscale
- Accessible: Works from anywhere (VPN/home/office)
- No public IP exposure: All nodes on private Tailscale network
- Zero-trust: Tailscale handles authentication + device verification

## Implementation Steps

### Phase 1: Prepare for Tailscale IPs

**Status:** Code already compatible

The Express server doesn't hardcode IPs—it uses environment variables:
- `ZABBIX_API_URL`: Can be `http://zabbix.tailscale.local/api_jsonrpc.php`
- `PROXMOX_HOST`: Can be `proxmox.tailscale.local`

No code changes needed; just update `.env` for Tailscale deployment.

### Phase 2: Tailscale Machine Setup (When Ready)

1. **Zabbix Machine**
   ```bash
   # On Zabbix host
   tailscale up --advertise-exit-node=false
   # Assign DNS: zabbix.tailscale.local
   ```

2. **Proxmox Machine**
   ```bash
   # On pve-r720
   tailscale up
   # Assign DNS: proxmox.tailscale.local
   ```

3. **Inframon Machine** (LXC or Proxmox box)
   ```bash
   # Install Tailscale in container/VM
   curl -fsSL https://tailscale.com/install.sh | sh
   tailscale up
   # Assign DNS: inframon.tailscale.local

   # Firewall: Allow 443 (HTTPS) + 3001 (API)
   ufw allow 443
   ufw allow 3001
   ```

### Phase 3: HTTPS Certificate

Tailscale provides automatic HTTPS via Let's Encrypt integration.

**For Inframon Web UI:**
```typescript
// src/server.ts - when on Tailscale
import https from 'https';
import fs from 'fs';

const certDir = '/var/lib/tailscale'; // Tailscale cert location
const options = {
  key: fs.readFileSync(`${certDir}/key.pem`),
  cert: fs.readFileSync(`${certDir}/cert.pem`),
};

https.createServer(options, app).listen(3001);
```

Or use Caddy as reverse proxy (simpler):
```
https://inframon.tailscale.local {
  reverse_proxy localhost:3000
  reverse_proxy /api/* localhost:3001
}
```

### Phase 4: Update Environment

**.env for Tailscale:**
```env
ZABBIX_API_URL=http://zabbix.tailscale.local/api_jsonrpc.php
PROXMOX_HOST=proxmox.tailscale.local
INFRAMON_WEB_URL=https://inframon.tailscale.local
```

### Phase 5: Access Control

Tailscale ACLs can restrict access per user/device:

```json
{
  "acls": [
    {
      "action": "accept",
      "src": ["autogroup:members"],
      "dst": ["inframon.tailscale.local:443", "zabbix.tailscale.local:80", "proxmox.tailscale.local:22"],
      "ports": ["*:*"]
    }
  ]
}
```

## Migration Path

### Step 1: Coexistence (Current)
- Polling: Direct to 10.10.1.142 (internal network)
- Web UI: Direct to localhost:3000
- Works for local LAN access

### Step 2: Tailscale Parallel
- Add Tailscale to all machines
- Keep direct access working
- Deploy inframon to Tailscale-connected machine
- Both paths work simultaneously

### Step 3: Tailscale Primary
- Update all `.env` to use `*.tailscale.local` domains
- Keep direct access as fallback
- Phase out direct IP access

### Step 4: Tailscale Only
- Remove direct IP references
- Enforce Tailscale-only access
- Decommission direct network paths

## Code Changes (When Implemented)

### Current (No Changes Needed)
```typescript
// src/server.ts already uses env vars
const ZABBIX_API_URL = process.env.ZABBIX_API_URL;
const PROXMOX_HOST = process.env.PROXMOX_HOST;
```

### Future (HTTPS Support)
```typescript
// Add optional HTTPS when Tailscale certs available
if (process.env.TAILSCALE_CERT_PATH) {
  const https = require('https');
  const fs = require('fs');
  https.createServer({
    key: fs.readFileSync(`${process.env.TAILSCALE_CERT_PATH}/key.pem`),
    cert: fs.readFileSync(`${process.env.TAILSCALE_CERT_PATH}/cert.pem`),
  }, app).listen(process.env.PORT_API || 3001);
} else {
  app.listen(process.env.PORT_API || 3001);
}
```

## Testing Checklist (When Ready)

- [ ] All Tailscale machines have `tailscale status` showing online
- [ ] DNS resolution: `nslookup inframon.tailscale.local` works
- [ ] SSH from inframon to proxmox works: `ssh root@proxmox.tailscale.local`
- [ ] Zabbix API reachable: `curl http://zabbix.tailscale.local/api_jsonrpc.php`
- [ ] Web UI accessible: `https://inframon.tailscale.local`
- [ ] Alert flow works end-to-end
- [ ] Remove direct IP access, test Tailscale-only mode

## Security Notes

- **No firewall changes needed:** Tailscale handles encryption
- **Device authentication:** Only Tailscale members can access
- **Audit log:** Tailscale logs all access for compliance
- **MFA optional:** Can require device key verification

## Related

See [ARCHITECTURE.md](./ARCHITECTURE.md) for current topology.
