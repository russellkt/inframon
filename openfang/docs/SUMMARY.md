# OpenFang Quick Reference

A concise summary of the OpenFang Agent Operating System, designed to get new Claude Code sessions up to speed without reading 18 separate docs.

## What is OpenFang?

OpenFang is the **open-source Agent Operating System** — a Rust-based platform for building, deploying, and managing autonomous AI agents. Key numbers: 14 crates, 40 messaging channels, 60 bundled skills, 20 LLM providers, 76 API endpoints, 16 security systems.

**Core principle**: Agents are deployed specialists that work autonomously, not just chatbots waiting for your messages.

---

## Installation & Setup

```bash
# Initialize workspace
openfang init          # Creates ~/.openfang/ with config.toml
openfang init --quick  # Non-interactive (useful for CI)

# Set API key
export GROQ_API_KEY="gsk_..."  # Or any of 20 providers (Anthropic, OpenAI, Gemini, etc.)

# Start daemon
openfang start         # Boots kernel + HTTP API on http://127.0.0.1:4200

# Quick chat
openfang chat          # Chat with default agent
```

---

## Core Concepts

### Agents
Agents are autonomous AI instances that can be spawned, configured, and monitored. Each agent:
- Runs on a specific LLM provider/model
- Has a system prompt and capabilities manifest
- Can access tools, call skills, and interact via channels
- Persists state (memory, sessions) in SQLite

**Spawning an agent**:
```bash
openfang agent new <template>    # From built-in templates
openfang agent spawn manifest.toml  # From custom manifest
openfang agent list              # See running agents
openfang agent chat <id>         # Chat with an agent
```

### Skills
Skills are pluggable tool bundles that extend agent capabilities. OpenFang ships with **60 bundled skills** (Python/WASM/Node.js/prompt-only, compiled into the binary).

**Installing a skill**:
```bash
openfang skill install web-summarizer  # From FangHub
openfang skill install ./my-skill/     # From local directory
```

### Hands (Autonomous Capability Packages)
Unlike regular agents (chat-driven), Hands are **autonomous specialists** that:
- Run on schedules or events (not just user messages)
- Accumulate knowledge over time
- Report progress to a dashboard
- Follow multi-phase operational playbooks

**7 bundled Hands**: Clip (content), Lead (sales), Collector (OSINT), Predictor (forecasting), Researcher (academic), Social (Twitter/X), Browser (web automation).

### Channels (40 messaging platforms)
Agents interact with users through channels: Discord, Telegram, Slack, WhatsApp, Signal, Matrix, Email, Mastodon, Bluesky, Reddit, LinkedIn, Teams, Mattermost, and 26 more.

**Setup**:
```bash
openfang channel setup telegram  # Interactive setup wizard
openfang channel list            # Check channel status
```

### Workflows
Multi-step agent pipelines. Chain agents sequentially, fan-out parallel tasks, conditionally branch, or loop with quality gates.

**Example**: research → outline → write → fact-check (with conditional skip if no claims found)

### Hands vs Regular Agents

| Dimension | Agent | Hand |
|-----------|-------|------|
| Trigger | User message | Schedule/event/manual activation |
| Lifecycle | Single request-response | Long-running with phases |
| Knowledge | Fresh per conversation | Accumulates via SKILL.md |
| Configuration | Prompt engineering | Declarative HAND.toml |
| Monitoring | Chat log | Dashboard metrics + API |
| Autonomy | Responds when asked | Operates independently |

---

## Configuration Files

### config.toml
Main config at `~/.openfang/config.toml`:

```toml
[default_model]
provider = "groq"           # anthropic, openai, gemini, etc.
model = "llama-3.3-70b-versatile"
api_key_env = "GROQ_API_KEY"

[network]
listen_addr = "127.0.0.1:4200"

[memory]
decay_rate = 0.05

[channels.discord]
bot_token_env = "DISCORD_BOT_TOKEN"
default_agent = "inframon"

[channels.webhook]
secret_env = "WEBHOOK_SECRET"
default_agent = "inframon"

[[mcp_servers]]
name = "github"
[mcp_servers.transport]
type = "stdio"
command = "npx"
args = ["-y", "@modelcontextprotocol/server-github"]
```

### agent.toml (Agent Manifests)
Defines an agent's identity, capabilities, and LLM config:

```toml
name = "inframon"
version = "0.1.0"
description = "Infrastructure monitoring agent"
author = "your-org"
module = "builtin:chat"  # Agent module type

[model]
provider = "openrouter"
model = "qwen/qwen-3.5-35b"
api_key_env = "OPENROUTER_API_KEY"

[capabilities]
tools = ["file_read", "web_fetch", "shell_exec"]
memory_read = ["*"]
memory_write = ["self.*"]

[resources]
max_iterations = 20
max_llm_tokens_per_hour = 100000

skills = ["juniper-query", "zabbix-query", "proxmox-query"]
```

### SKILL.md (Expert Knowledge)
Markdown with YAML frontmatter. Gets injected into agent's system prompt:

```markdown
---
name: rust-expert
description: Expert Rust programming knowledge
---

# Rust Expert

## Key Principles
- Ownership and borrowing rules...
- Lifetime annotations...
```

### HAND.toml (Autonomous Packages)
Declares what a Hand needs and how it's configured:

```toml
[hand]
id = "lead-generator"
name = "Lead Generator"
description = "Autonomous lead generation engine"
category = "sales"
version = "0.1.0"

[hand.requires]
tools = ["web_fetch", "web_search"]
capabilities = ["NetConnect(*)"]

[hand.settings]
[hand.settings.icp]
type = "string"
description = "Your ideal customer profile"

[hand.agent]
provider = "openai"
model = "gpt-4o"
temperature = 0.7

[hand.schedule]
cron = "0 9 * * MON"  # Every Monday at 9 AM

[hand.dashboard]
metrics = ["leads_found", "leads_scored", "qualified_count"]
```

---

## Agent Lifecycle

1. **Spawn** — Create agent from template or manifest
2. **Initialize** — Load config, system prompt, skills, capabilities
3. **Run loop** — Agent processes messages, calls tools, updates memory
4. **Pause/Resume** — Temporarily suspend (state preserved)
5. **Kill** — Terminate and free resources

**Agent loop basics**:
- LLM sees: system prompt + context window + available tools
- LLM decides: call a tool, or respond to user
- If tool call: execute in sandbox, feed result back to LLM
- Repeat until response is generated

---

## Skills System

### Discovery
Skills are loaded from:
1. `~/.openfang/skills/` (installed skills)
2. Bundled binary (60 pre-compiled skills)
3. Referenced in agent manifest's `skills = [...]` field

### SKILL.md Format (Prompt-Only Skills)
Parsed from YAML frontmatter + Markdown body. Auto-scanned for prompt injection before inclusion.

### Executable Skills (Python, WASM, Node.js)

**Directory structure**:
```
my-skill/
  skill.toml          # Manifest
  src/
    main.py           # Entry point (Python example)
  README.md
```

**skill.toml**:
```toml
[skill]
name = "my-skill"
version = "0.1.0"
description = "..."

[runtime]
type = "python"  # or "wasm", "node"
entry = "src/main.py"

[[tools.provided]]
name = "my_tool"
description = "Does something useful"
input_schema = { type = "object", properties = { param = { type = "string" } }, required = ["param"] }

[requirements]
tools = ["web_fetch"]  # Built-in tools this skill needs
capabilities = ["NetConnect(*)"]
```

**Python skill protocol** (stdin/stdout JSON):
```python
import json
import sys

payload = json.loads(sys.stdin.read())
tool_name = payload["tool"]
input_data = payload["input"]

result = handle_tool(tool_name, input_data)
print(json.dumps({"result": result}))  # or {"error": "message"}
```

### Auto-Conversion from OpenClaw
OpenFang auto-detects and converts OpenClaw-format skills (Node.js + package.json).

---

## Channels (Messaging Integration)

OpenFang connects to **40 messaging platforms**. All use common patterns:
- Configuration in `config.toml` under `[channels.<name>]`
- Secrets stored as env var references (e.g., `token_env = "DISCORD_BOT_TOKEN"`)
- Per-channel overrides (model, system prompt, DM/group policy, rate limiting)

### Core 7 Channels
| Channel | Setup | Notes |
|---------|-------|-------|
| **Discord** | Bot token + Message Content Intent enabled | WebSocket Gateway v10 |
| **Telegram** | Bot token from @BotFather | Long-polling |
| **Slack** | Bot token + App token (Socket Mode) | WebSocket + REST |
| **WhatsApp** | Meta Business account + webhook | Cloud API |
| **Signal** | signal-cli service | JSON-RPC subprocess |
| **Matrix** | Homeserver token | Client-Server API |
| **Email** | IMAP + SMTP creds | Gmail app passwords work |

### Setup Wizard
```bash
openfang channel setup <channel>
# Steps: get credentials → set env vars → update config.toml
```

### Channel Overrides (Per-Channel Customization)
```toml
[channels.discord.overrides]
model = "gemini-2.5-flash"
system_prompt = "Concise Discord-friendly responses"
dm_policy = "respond"           # respond | allowed_only | ignore
group_policy = "mention_only"   # all | mention_only | commands_only | ignore
rate_limit_per_user = 10        # msgs/minute
threading = true
output_format = "markdown"      # markdown | telegram_html | slack_mrkdwn | plaintext
usage_footer = "compact"
```

---

## API Essentials

### Health & Status
```
GET /api/health                 # Basic health check
GET /api/status                 # Daemon status + agent count
```

### Agent Management
```
POST /api/agents                # Spawn agent (send TOML)
GET /api/agents                 # List all agents
GET /api/agents/{id}            # Get agent details
POST /api/agents/{id}/message   # Send message to agent
GET /api/agents/{id}/sessions   # List sessions
POST /api/agents/{id}/kill      # Terminate agent
```

### WebSocket Chat (Real-Time)
```
WS ws://127.0.0.1:4200/api/agents/{id}/ws
```
Send: `{"type": "message", "text": "hello"}`
Receive: streaming text deltas + token counts

### Workflows
```
POST /api/workflows             # Create workflow
GET /api/workflows              # List workflows
POST /api/workflows/{id}/run    # Execute (blocks until done)
GET /api/workflows/{id}/runs    # List past runs
```

### Triggers (Event-Driven)
```
POST /api/triggers              # Create trigger
GET /api/triggers               # List triggers
PUT /api/triggers/{id}          # Enable/disable
DELETE /api/triggers/{id}       # Delete
```

### Skills
```
GET /api/skills                 # List installed
POST /api/skills/install        # Install from FangHub/git/local
DELETE /api/skills/{name}       # Remove
```

### Channels
```
GET /api/channels               # List with status
POST /api/channels/{name}/test  # Test channel
POST /api/channels/{name}/enable
POST /api/channels/{name}/disable
```

### OpenAI-Compatible API
```
POST /v1/chat/completions       # Claude SDK compatible
# model: "openfang:agent-name"
```

---

## CLI Essentials

### Agent Commands
```bash
openfang agent new <template>           # Spawn from template
openfang agent spawn <manifest>         # Spawn from file
openfang agent list                     # List running
openfang agent chat <id>                # Interactive chat
openfang agent kill <id>                # Terminate
```

### Workflow & Trigger Commands
```bash
openfang workflow list                  # List workflows
openfang workflow create <file.json>    # Create from JSON
openfang workflow run <id> "<input>"    # Execute

openfang trigger list                   # List triggers
openfang trigger create <agent> <pattern> --prompt "..." --max-fires N
openfang trigger delete <id>            # Delete
```

### Skill Commands
```bash
openfang skill list                     # List installed
openfang skill install <source>         # Install
openfang skill remove <name>            # Remove
openfang skill search <query>           # Search FangHub
openfang skill create                   # Interactive scaffold
```

### Channel Commands
```bash
openfang channel list                   # List all
openfang channel setup <channel>        # Interactive setup
openfang channel test <channel>         # Test
openfang channel enable/disable <name>  # Toggle
```

### Config Commands
```bash
openfang config show                    # Display config
openfang config edit                    # Open in editor
openfang config get <key>               # Get value by path
openfang config set <key> <value>       # Set value
openfang config set-key <provider>      # Interactive API key setup
openfang config test-key <provider>     # Test key validity
```

### Diagnostics
```bash
openfang status                         # Daemon status
openfang doctor                         # Run all checks
openfang doctor --repair                # Auto-fix issues
openfang doctor --json                  # Machine-readable
```

### MCP Integration
```bash
openfang mcp                            # Start MCP server (stdio)
```

---

## Workflows: Multi-Step Pipelines

### Step Modes
- **sequential** (default) — step after step, passing output as input
- **fan_out** — run parallel, receive same input
- **collect** — join fan-out outputs with "---" separator
- **conditional** — skip if previous output doesn't contain condition substring
- **loop** — repeat up to max_iterations, exit early if `until` substring found

### Variable Substitution
- `{{input}}` — output from previous step
- `{{variable_name}}` — use `"output_var": "name"` to store step output for later reference

### Error Handling
- **fail** (default) — abort workflow
- **skip** — silently skip on error, keep previous input
- **retry** — retry N times before giving up

### Example Workflow (JSON)
```json
{
  "name": "code-review",
  "steps": [
    {
      "name": "analyze",
      "agent_name": "coder",
      "prompt": "Analyze:\n{{input}}",
      "mode": "sequential",
      "timeout_secs": 120,
      "error_mode": "fail",
      "output_var": "analysis"
    },
    {
      "name": "fact-check",
      "agent_name": "verifier",
      "prompt": "Check:\n{{analysis}}",
      "mode": "conditional",
      "condition": "error",
      "error_mode": "skip"
    }
  ]
}
```

---

## Triggers & Event-Driven Automation

### Trigger Patterns
- `"all"` — every event
- `"lifecycle"` — agent spawned/terminated
- `{"agent_spawned": {"name_pattern": "coder"}}` — specific agent
- `"agent_terminated"` — any agent dies
- `"system"` — system events (health, quota)
- `{"content_match": {"substring": "error"}}` — text match

### Example Trigger
Monitor agent health:
```bash
openfang trigger create <agent-id> \
  '{"content_match": {"substring": "health check failed"}}' \
  --prompt "ALERT: {{event}}. Investigate all agents." \
  --max-fires 0
```

---

## MCP (Model Context Protocol)

### MCP as Client (OpenFang → External Tools)
OpenFang connects to external MCP servers (GitHub, filesystem, databases, Puppeteer, etc.). Tools get namespaced: `mcp_github_create_issue`, `mcp_filesystem_read`.

**Config**:
```toml
[[mcp_servers]]
name = "github"
timeout_secs = 30
env = ["GITHUB_PERSONAL_ACCESS_TOKEN"]

[mcp_servers.transport]
type = "stdio"
command = "npx"
args = ["-y", "@modelcontextprotocol/server-github"]
```

Auto-connects at kernel boot. All agents see MCP tools in `available_tools()`.

### MCP as Server (External Tools → OpenFang)
Expose OpenFang agents as MCP tools:

```bash
openfang mcp  # Starts stdio MCP server
```

**For Claude Desktop**:
```json
{
  "mcpServers": {
    "openfang": {
      "command": "openfang",
      "args": ["mcp"]
    }
  }
}
```

Each agent becomes a tool: `openfang_agent_inframon`, `openfang_agent_coder`, etc.

### Protocol
JSON-RPC 2.0 over Content-Length framed stdio. Methods: `initialize`, `tools/list`, `tools/call`.

---

## A2A (Agent-to-Agent Protocol)

OpenFang implements Google's A2A protocol for cross-framework agent interoperability.

### Agent Card (Capability Advertisement)
Published at `/.well-known/agent.json`. Describes agent's name, description, capabilities, skills.

### A2A Endpoints
```
GET /.well-known/agent.json         # Agent Card
GET /a2a/agents                     # List all agents
POST /a2a/tasks/send                # Submit task to agent
GET /a2a/tasks/{id}                 # Poll task status
POST /a2a/tasks/{id}/cancel         # Cancel
```

### Configuration
```toml
[a2a]
enabled = true
listen_path = "/a2a"

[[a2a.external_agents]]
name = "research-agent"
url = "https://research.example.com"
```

---

## Hands vs Regular Agents (Detailed)

### Traditional Agent
- Triggered by user message
- Single request-response cycle
- Starts fresh each time
- Configured via prompt engineering
- No built-in persistence between sessions

### Hand (Autonomous Specialist)
- Triggered by schedule (cron), event, or manual activation
- Multi-phase operational playbook
- Accumulates knowledge in knowledge graphs
- Declarative HAND.toml manifest + SKILL.md
- Dashboard with custom metrics
- Long-running with explicit phases and quality gates

### Building a Hand
1. Create `HAND.toml` — manifest with tools, settings, schedule, dashboard config
2. Create `system-prompt.md` — multi-phase procedures
3. Create `SKILL.md` (optional) — expert domain knowledge
4. Install and activate via CLI

---

## Troubleshooting & Common Gotchas

### Agent Stuck in Loop
Auto-protected: warns at 3 identical tool calls, blocks at 5, circuit breaks at 30.
Manual fix: `curl -X POST http://127.0.0.1:4200/api/agents/{id}/stop`

### Context Window Exhausted
Auto-compact when threshold reached. Manual: `/compact` command or `POST /api/agents/{id}/session/compact`

### Agent Not Using Tools
Check manifest `[capabilities].tools = [...]` — must explicitly list each tool.

### Port Already in Use
Change in config: `[network]` → `listen_addr = "127.0.0.1:3001"`

### LLM API Key Issues
```bash
openfang config set-key <provider>  # Interactive prompt
openfang config test-key <provider> # Validate
openfang doctor                     # Full diagnostic
```

### Channel Not Responding
- Check token is set and valid: `echo $TELEGRAM_BOT_TOKEN`
- Restart daemon after config changes
- Check logs: `RUST_LOG=openfang_channels=debug openfang start`

### Workflow Step Timeouts
Increase `timeout_secs` per step (default 120). Each retry gets fresh timeout budget.

---

## Environment Variables

**LLM Providers** (set ONE):
```bash
GROQ_API_KEY=gsk_...
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=...
OPENROUTER_API_KEY=...
```

**Channel Tokens**:
```bash
DISCORD_BOT_TOKEN=...
TELEGRAM_BOT_TOKEN=...
SLACK_BOT_TOKEN=...
SLACK_APP_TOKEN=...
```

**Logging**:
```bash
RUST_LOG=info              # info, debug, trace
RUST_LOG=openfang=debug    # Specific crates
```

---

## Deployment (inframon context)

For the inframon project running in Docker:

```toml
# openfang/config.toml
[default_model]
provider = "openrouter"
model = "qwen/qwen-3.5-35b"
api_key_env = "OPENROUTER_API_KEY"

[network]
listen_addr = "0.0.0.0:4200"

[channels.discord]
bot_token_env = "DISCORD_BOT_TOKEN"
default_agent = "inframon"

[channels.webhook]
secret_env = "WEBHOOK_SECRET"
default_agent = "inframon"

[[mcp_servers]]
name = "my-tools"
[mcp_servers.transport]
type = "stdio"
command = "python"
args = ["-m", "some_mcp_server"]
```

Skills mounted at `/data/skills` (via `$OPENFANG_HOME` = `/data`). Agents auto-discover skills from manifest `skills = [...]` field.

---

## Quick Reminders

- **Agents** are chat-driven specialists you interact with
- **Hands** are autonomous workers on schedules
- **Skills** are tool bundles (60 built-in, can install more)
- **Workflows** chain agents together in multi-step pipelines
- **Channels** connect agents to Discord, Telegram, etc. (40 platforms)
- **Triggers** fire agents when events occur
- **MCP** lets agents use external tools (GitHub, databases, etc.)
- **A2A** lets different agent frameworks talk to each other

All state persists in SQLite (`~/.openfang/data/openfang.db`). Configuration is TOML + environment variables. The daemon is stateful; agents survive daemon restarts.

---

## Key Resources

- **[Architecture](architecture.md)** — 12-crate structure, kernel, memory substrate
- **[Configuration](configuration.md)** — Every config.toml field reference
- **[Skill Development](skill-development.md)** — Build Python/WASM/Node skills
- **[Channel Adapters](channel-adapters.md)** — 40 channels, setup, custom adapters
- **[Hands](hands.md)** — Autonomous specialist system
- **[Workflows](workflows.md)** — Multi-step pipelines + trigger engine
- **[API Reference](api-reference.md)** — All 76 REST/WS/SSE endpoints
- **[CLI Reference](cli-reference.md)** — Complete command reference
- **[Troubleshooting](troubleshooting.md)** — Common issues + FAQ
- **[MCP & A2A](mcp-a2a.md)** — Protocol integration details
