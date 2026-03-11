# Architecture

## System Design

```
┌─────────────────────────────────────────────────────────┐
│                     Zabbix Server                       │
│   - Collects metrics from hosts                        │
│   - Detects problems via triggers                      │
│   - Exposes API for querying                           │
└────────────────┬────────────────────────────────────────┘
                 │ (poll every 5m)
                 ↓
┌─────────────────────────────────────────────────────────┐
│              Inframon Agent (pi-based)                  │
│                                                         │
│  - Polls Zabbix for unacknowledged problems           │
│  - Generates notifications                             │
│  - Provides investigation via skills                   │
│  - Persists alert history in ak                        │
└────────────────┬────────────────────────────────────────┘
                 │
         ┌───────┴──────────┐
         ↓                  ↓
    ┌─────────────┐  ┌───────────────┐
    │   Slack     │  │   Email       │
    │ Notification│  │ Notification  │
    └─────────────┘  └───────────────┘
         │                  │
         │   (contains       │   (contains
         │    web link)      │    web link)
         │                  │
         └──────────┬───────┘
                    ↓
    http://localhost:3000?alert_id=123&host=ex3400
                    │
                    ↓
    ┌─────────────────────────────────────────────────────┐
    │           Web UI (pi-web-ui ChatPanel)              │
    │                                                     │
    │  - Renders alert context in chat                   │
    │  - Streams agent investigation                     │
    │  - Session storage (IndexedDB)                     │
    │  - Human approval for remediation                  │
    └────────────┬────────────────────────────────────────┘
                 │
         ┌───────┴──────────┐
         ↓                  ↓
    ┌─────────────┐  ┌───────────────┐
    │  Proxmox    │  │   Zabbix      │
    │  APIs       │  │   APIs        │
    │  (VM status)│  │  (Acknowledge)│
    └─────────────┘  └───────────────┘
```

## Components

### 1. Inframon Agent (pi-based)

**Purpose:** Monitor Zabbix and investigate problems

**Process:**
1. Poll Zabbix API every 5 minutes
2. Query for `problem.get` with unacknowledged severity >= Warning
3. For each problem:
   - Generate alert notification with web UI link
   - Store alert context in ak (agent-knowledge)
4. Wait for next poll interval

**Skills:**
- `zabbix-ops` — Query Zabbix API
- `proxmox-admin` — Query Proxmox cluster
- `junos-config` — Query Juniper switches

**Dependencies:**
- Zabbix API endpoint + token
- Proxmox API endpoint + token

### 2. Web UI (pi-web-ui)

**Purpose:** Chat interface for human-in-the-loop investigation

**Technology:**
- Lit web components
- ChatPanel from `@mariozechner/pi-web-ui`
- IndexedDB for session persistence
- Vite for bundling

**Features:**
- Pre-populate alert context from URL params
- Stream agent responses in real-time
- Session history
- Model/API key configuration
- Theme toggle

**Entry Points:**
- `/` — New chat session
- `/?session=uuid` — Resume session
- `/?alert_id=123&host=ex3400` — Pre-populated alert

### 3. Alert Context Storage

**Current:** In-memory per session (IndexedDB)
**Future:** Persist to ak (agent-knowledge) for cross-session history

Each alert stores:
```typescript
{
  alert_id: string,
  host: string,
  problem_type: string,
  severity: string,
  created_at: timestamp,
  conversation: AgentMessage[],
  resolution: string,
  resolved_at: timestamp,
}
```

### 4. Integration Points

#### Slack/Email Notification

Inframon agent generates links:
```
⚠️ EX3400 interface down
[Troubleshoot] (http://localhost:3000?alert_id=123&host=ex3400&problem=interface-down)
```

#### Zabbix Acknowledgement

When human confirms resolution via chat:
```
Agent: "Should I acknowledge this problem in Zabbix?"
Human: "Yes"
Agent: [acknowledges via zabbix-ops skill]
```

#### Remediation Actions

Examples:
- Proxmox: Restart VM
- Juniper: Reset interface
- Zabbix: Update threshold

**Policy:** Only after explicit human approval

## Data Flow

### Alert Detection → Notification

```
1. inframon polls Zabbix
2. Finds unacknowledged problem
3. Constructs notification:
   {
     "host": "ex3400",
     "problem": "interface-down",
     "severity": "High",
     "link": "http://localhost:3000?alert_id=123&host=ex3400"
   }
4. Sends via Slack/email
5. Stores in ak for history
```

### Investigation → Resolution

```
1. Human clicks link → Web UI loads
2. Alert context pre-populated in chat
3. Human: "What's the status?"
4. Agent:
   - Queries zabbix-ops for details
   - Queries proxmox-admin for related issues
   - Streams findings
5. Human: "Restart the interface"
6. Agent: "Acknowledging approval, executing..."
7. Agent: [uses junos-config to reset interface]
8. Agent: "Interface restarted. Monitoring for recovery."
9. Human: "Looks good, thanks"
10. Session archived in ak
```

## Skill System

Each skill is a markdown file (`.pi/agent/skills/`) describing available tools:

### zabbix-ops.md

```markdown
# zabbix-ops

Query Zabbix API...

## Tools

### query-problems
Get unacknowledged problems...
```

**Implementation:** Skill definitions reference tools that pi agent core resolves at runtime.

### Adding Custom Skill

1. Create `.pi/agent/skills/my-skill.md`
2. Define tools and parameters
3. Reference in `.pi/agent/agents/inframon.md`:
   ```yaml
   skills:
     - zabbix-ops
     - my-skill
   ```

## Session Persistence

**Browser Storage:** IndexedDB
- Survives page refresh
- Survives browser close
- Persists across days

**Cloud Storage (Future):** ak (agent-knowledge)
- Shared across sessions/machines
- Full-text search
- Long-term history

**URL State:**
- Session ID in query param: `?session=uuid`
- Alert context in query params: `?alert_id=123&host=ex3400`
- Allows sharing specific investigation

## Error Handling

**Agent Failures:**
- Skill timeout → retry with backoff
- Invalid token → notify + stop polling
- Network error → log + continue next poll

**Web UI Failures:**
- API key missing → prompt user
- Session load fails → new blank session
- Storage quota exceeded → archive old sessions

**Notification Failures:**
- Slack webhook down → log + retry
- Email delivery failed → fallback to logs

## Security Considerations

### API Tokens

**In Docker:**
- Stored in `.env` (mounted volume)
- Passed via environment variables
- Never logged or exposed

**In Web UI:**
- API keys for AI provider (user enters via settings)
- Stored in IndexedDB (browser local storage)
- Never sent to backend

### Zabbix/Proxmox Access

- Read-only for investigations (safe)
- Remediation requires explicit human approval
- All actions logged for audit

### Network

- Inframon ↔ Zabbix: Internal network (bmic-infra)
- Web UI ↔ Inframon agent: Local (within container)
- Web UI → AI APIs: User's API key (direct from browser)

## Deployment Topology

### Development

```
localhost:3000 (vite dev server)
    ↓
pi daemon (polling)
    ↓
Zabbix / Proxmox (local IPs)
```

### Production (Docker)

```
inframon container (Docker)
    ├─ Web UI (port 3000)
    └─ Agent daemon (background process)
        ↓
    Zabbix / Proxmox (bmic-infra network)
```

### Future: Proxmox LXC

```
Ubuntu 22.04 LXC container
    ↓
Docker daemon
    ↓
Inframon container (same as above)
```

## Scaling Considerations

**Current:** Single inframon agent, single web UI instance

**Future:**
- Load balancer for web UI (multiple replicas)
- Shared session storage (PostgreSQL instead of IndexedDB)
- Multiple agents for different datacenters
- Webhook integration (Slack/email sends directly to web UI instead of link)

## Related Projects

- **bmic-proxmox** — Infrastructure platform
- **pi-mono** — Agent framework
- **agent-knowledge (ak)** — Shared history + knowledge store

See [SETUP.md](./SETUP.md) for configuration.
