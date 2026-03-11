# Related Projects & Documentation

This project integrates with several other systems. Reference their documentation for deeper context.

## bmic-proxmox

**Location:** `~/git/bmic-proxmox`

**Relevant Documentation:**
- Infrastructure architecture (Proxmox nodes, storage, networking)
- Zabbix configuration (hosts, triggers, items)
- Juniper switch setup (EX2300, EX3400)
- PBS backup configuration
- Network topology and VLANs

**Key Files:**
```
bmic-proxmox/
├── docs/
│   ├── infrastructure.md      # Overall platform architecture
│   ├── zabbix-hosts.md        # Monitored hosts and triggers
│   ├── switches.md            # Network switches (EX2300, EX3400)
│   ├── proxmox-nodes.md       # Cluster nodes (pve-r720, pve-p520, etc)
│   └── networking.md          # VLANs, IP ranges, connectivity
├── plans/                     # Implementation plans
└── configs/                   # Zabbix configs, network device configs
```

**From Inframon Perspective:**
- Reference `zabbix-hosts.md` to understand what's being monitored
- Check `switches.md` for Juniper topology (which ports matter)
- Review `proxmox-nodes.md` for cluster health metrics
- Look at network topology for understanding dependencies

## pi-mono

**Location:** `~/git/pi-mono` (or `npm: @mariozechner/pi-*`)

**Relevant Documentation:**
- Agent framework documentation
- Skill system (how to write `.pi/agent/skills/`)
- Tool calling and LLM integration
- Web UI component library (pi-web-ui)

**Key Packages:**
- `@mariozechner/pi-ai` — LLM provider integration
- `@mariozechner/pi-agent-core` — Agent state management
- `@mariozechner/pi-web-ui` — ChatPanel and components
- `@mariozechner/pi-tui` — Terminal UI (for CLI agent)

**From Inframon Perspective:**
- Use pi as the agent framework (already doing this)
- Extend with custom skills (see `README.md`)
- Use web-ui for the chat interface (already integrated)

## agent-knowledge (ak)

**Location:** `~/git/agent-knowledge`

**CLI:** `ak` (if installed globally)

**Relevant Documentation:**
- Knowledge store schema
- How to query and store findings
- Integration with agents for persistent learning

**From Inframon Perspective:**
- Store alert investigation results in ak for long-term history
- Query ak for similar past incidents
- Build knowledge base of infrastructure patterns

**Commands:**
```bash
# Search for past incidents
ak recall "ex3400 interface down" -n 10

# Store investigation findings
ak store "EX3400 ge-0/0/48 down due to loose SFP connector" \
  -p bmic-infra-monitor \
  -t error_fix
```

## Email Processor

**Location:** `~/git/email-processor`

**Purpose:** Process 176K+ emails with FTS + vector search

**From Inframon Perspective:**
- Could integrate for email-based notifications
- Could search past emails for incident context
- Could archive investigation emails automatically

## How to Use This Documentation

### New to the Project?

1. Read `README.md` (quick overview)
2. Follow `docs/SETUP.md` (getting started)
3. Review `docs/ARCHITECTURE.md` (how it works)

### Understanding Infrastructure?

→ Check `bmic-proxmox/docs/` for:
- What's being monitored
- How systems are configured
- Network topology and dependencies

### Extending Inframon?

→ Check `pi-mono/packages/` for:
- Agent framework examples
- Skill system documentation
- Web UI component API

### Building Long-term Knowledge?

→ Use `ak` to:
- Store incident investigations
- Query for similar problems
- Build patterns and decisions

## Creating Symlinks (Optional)

If you want easy access to bmic-proxmox docs:

```bash
cd ~/git/inframon/docs
ln -s ../../bmic-proxmox/docs bmic-proxmox-ref
```

Then:
```bash
# Read directly
cat docs/bmic-proxmox-ref/infrastructure.md

# Or in your IDE
# Open docs/bmic-proxmox-ref/
```

## Key Concepts Across Projects

### Alert Flow

```
Zabbix (bmic-proxmox) →
Inframon (this project) →
Human Investigation (web UI) →
Remediation (Proxmox/Juniper APIs via bmic-proxmox tools) →
Knowledge Store (ak)
```

### Infrastructure Model

```
Physical Hosts (bmic-proxmox infrastructure)
    ↓
Proxmox Cluster (managed by bmic-proxmox)
    ↓
VMs/Containers (run on cluster)
    ↓
Services (monitored by Zabbix via bmic-proxmox)
    ↓
Alerts (detected by Zabbix)
    ↓
Troubleshooting (inframon + human)
    ↓
Resolution (action + learning)
```

## Next Steps

1. **Understand your infrastructure** → Read bmic-proxmox docs
2. **Set up inframon** → Follow SETUP.md
3. **Extend with skills** → Use pi-mono examples
4. **Build knowledge** → Use ak to store patterns
