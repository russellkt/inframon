Title: OpenFang — The Agent Operating System

URL Source: https://www.openfang.sh/docs/hands

Markdown Content:
Hands: Autonomous Capability Packages
-------------------------------------

Hands are OpenFang's core innovation — a fundamentally new primitive for building autonomous agents. Unlike every other agent framework where you chat with an agent and it responds, Hands **work for you**. They run on schedules, build knowledge over time, and report results to your dashboard. You activate a Hand and check in on its progress, the same way you'd manage an employee.

This is not prompt engineering. This is not a chatbot wrapper. Hands are curated, self-contained autonomous packages that combine configuration, expert knowledge, operational playbooks, and tool access into a single deployable unit.

Table of Contents
-----------------

*   -[Why Hands Exist](https://www.openfang.sh/docs/hands#why-hands-exist)
*   -[Hands vs Traditional Agents](https://www.openfang.sh/docs/hands#hands-vs-traditional-agents)
*   -[The Three-Layer Architecture](https://www.openfang.sh/docs/hands#the-three-layer-architecture)
*   -[Bundled Hands](https://www.openfang.sh/docs/hands#bundled-hands)
*   -[Hand Lifecycle](https://www.openfang.sh/docs/hands#hand-lifecycle)
*   -[Build Your Own Hand](https://www.openfang.sh/docs/hands#build-your-own-hand)
*   -[HAND.toml Reference](https://www.openfang.sh/docs/hands#handtoml-reference)
*   -[System Prompt Design](https://www.openfang.sh/docs/hands#system-prompt-design)
*   -[SKILL.md Format](https://www.openfang.sh/docs/hands#skillmd-format)
*   -[Publishing to FangHub](https://www.openfang.sh/docs/hands#publishing-to-fanghub)

* * *

Why Hands Exist
---------------

Every agent framework today follows the same paradigm: you type a message, the agent processes it, and returns a response. This is fundamentally a **conversation tool** — the agent does nothing unless you initiate.

Real work doesn't happen in conversations. Real work happens **continuously** — monitoring feeds, generating leads, processing data, publishing content, researching topics. The people and systems that create the most value operate autonomously with periodic check-ins, not through turn-by-turn chat.

Hands are OpenFang's answer to this gap. A Hand is an **autonomous capability package** — a self-contained unit that knows what it needs to do, what tools it requires, how to operate across multiple phases, and how to report its progress. When you activate a Hand, it runs. On its schedule. With its tools. Building knowledge. Reporting metrics. You don't babysit it.

This is the difference between hiring an assistant you have to micromanage through chat, and deploying a specialist who knows their job.

Hands vs Traditional Agents
---------------------------

| Dimension | Traditional Agent | OpenFang Hand |
| --- | --- | --- |
| **Trigger** | User sends a message | Schedule, event, or manual activation |
| **Lifecycle** | Single request-response | Long-running with phases and checkpoints |
| **Knowledge** | Starts fresh each conversation | Accumulates via SKILL.md + knowledge graphs |
| **Configuration** | Prompt engineering | Declarative HAND.toml manifest |
| **Monitoring** | Read the chat log | Dashboard metrics, status API, event stream |
| **Autonomy** | Responds when asked | Operates independently on its schedule |
| **Expertise** | Generic unless carefully prompted | Domain expert via curated SKILL.md knowledge |
| **Reproducibility** | Varies with prompt phrasing | Deterministic manifest + versioned playbook |

The mental model shift: traditional agents are **tools you use**. Hands are **specialists you deploy**.

The Three-Layer Architecture
----------------------------

Every Hand is built from three layers, each serving a distinct purpose:

**Layer 1: HAND.toml** — _The job description._ A declarative manifest that defines what tools the Hand needs, what settings the user can configure, what metrics appear on the dashboard, and what system requirements must be met.

**Layer 2: System Prompt** — _The training manual._ A multi-phase operational playbook. Not a vague instruction — a concrete procedure manual with phases, decision trees, error recovery, and quality gates. The Hand follows this playbook autonomously.

**Layer 3: SKILL.md** — _The domain expertise._ Expert domain knowledge injected into the agent's context. Best practices, industry standards, evaluation criteria, known pitfalls. This is what makes the Hand a specialist, not a generalist.

All three layers are compiled into the OpenFang binary at build time via Rust's `include_str!()`. No external files to manage. No runtime dependencies. One binary, every Hand.

Bundled Hands
-------------

OpenFang ships with 7 production-ready Hands spanning content creation, data intelligence, forecasting, research, social media, and web automation.

### Clip — Content Creation

Turns long-form video into viral short clips. Fully autonomous 8-phase pipeline: source analysis, moment detection, clip extraction, caption generation, thumbnail creation, AI voice-over, quality scoring, and batch export. Uses FFmpeg and yt-dlp under the hood.

**Use cases:** Content repurposing, social media clips, highlight reels, podcast snippets.

### Lead — Data Intelligence

Autonomous lead generation engine. Discovers potential leads from configured sources, enriches them with company data and contact information, scores them 0-100 based on your ideal customer profile, and deduplicates against your existing pipeline. Runs daily by default.

**Use cases:** Sales pipeline, outbound prospecting, market research, competitive intelligence.

### Collector — OSINT Intelligence

Intelligence collection system inspired by OSINT methodology. Monitors any target (company, topic, person, technology) with automated change detection, sentiment tracking, and knowledge graph construction. Surfaces anomalies and trend shifts.

**Use cases:** Competitive monitoring, threat intelligence, market surveillance, brand monitoring.

### Predictor — Calibrated Forecasting

Superforecasting engine with calibrated probability estimates. Generates predictions with Brier scores, evidence chains, confidence intervals, and contrarian analysis. Tracks prediction accuracy over time and self-calibrates.

**Use cases:** Strategic planning, risk assessment, trend forecasting, decision support.

### Researcher — Deep Autonomous Research

Deep research agent with academic-grade methodology. CRAAP-test fact-checking (Currency, Relevance, Authority, Accuracy, Purpose), cross-reference verification, multi-language source support, and APA citation generation. Produces structured research reports.

**Use cases:** Market research, academic review, due diligence, technology assessment.

Autonomous Twitter/X account manager. 7 content types (thread, reply, quote, poll, announcement, engagement, commentary), approval queue for review before posting, engagement analytics tracking, and scheduled posting with optimal timing.

**Use cases:** Brand presence, thought leadership, community engagement, content distribution.

### Browser — Web Automation

Web automation powered by Playwright. Handles form filling, multi-step workflows, data extraction, and automated testing. Includes a mandatory purchase approval gate — the Hand will never complete a financial transaction without explicit human approval.

**Use cases:** Data scraping, form automation, testing workflows, price monitoring.

Hand Lifecycle
--------------

Hands follow a defined lifecycle managed through the CLI or API:

| State | Description | Transitions |
| --- | --- | --- |
| **Inactive** | Hand definition exists but is not running. No resources consumed. | `activate` moves to Active |
| **Active** | Running autonomously on its configured schedule. Processing tasks, building knowledge, reporting metrics. | `pause` moves to Paused, `deactivate` moves to Inactive |
| **Paused** | Temporarily suspended. State is preserved. Resume picks up exactly where it left off. | `resume` moves to Active, `deactivate` moves to Inactive |

Build Your Own Hand
-------------------

Building a custom Hand requires three files in a directory:

| File | Required | Purpose |
| --- | --- | --- |
| `HAND.toml` | Yes | Manifest — identity, tools, settings, schedule, dashboard metrics |
| `system-prompt.md` | Yes | Operational playbook — multi-phase procedures the Hand follows |
| `SKILL.md` | Recommended | Domain knowledge — expert reference injected into context |

### Step 1: Define the Manifest

Create `HAND.toml` with your Hand's identity, requirements, and configuration:

### Step 2: Write the Operational Playbook

Create `system-prompt.md` with concrete, multi-phase procedures:

### Step 3: Add Domain Knowledge (Optional)

Create `SKILL.md` with expert knowledge the Hand should reference:

### Advanced: Event-Driven Hands

Hands can respond to events in addition to (or instead of) schedules:

### Advanced: Multi-Hand Orchestration

Hands can chain together. The output of one Hand becomes the input to another:

### Advanced: Custom Dashboard Widgets

Define custom visualizations for your Hand's metrics:

### Step 4: Install and Activate

HAND.toml Reference
-------------------

The manifest is the single source of truth for what a Hand is, what it needs, and how it's configured.

| Section | Purpose |
| --- | --- |
| `[hand]` | Identity: id, name, description, category, icon, version |
| `[hand.requires]` | Dependencies: tools, capabilities, minimum OpenFang version |
| `[hand.settings]` | User-configurable options with types, defaults, and constraints |
| `[hand.agent]` | LLM configuration: model, temperature, max_iterations |
| `[hand.schedule]` | Cron expression for autonomous execution |
| `[hand.dashboard]` | Metrics and widgets exposed on the web dashboard |
| `[hand.triggers]` | Event-based activation (webhooks, file events) |
| `[hand.chain]` | Multi-Hand orchestration and data flow |

Settings support these types: `string`, `bool`, `int`, `float`, `string[]`. Each setting can have `default`, `options` (enum), `min`/`max` (numeric), and `description`.

System Prompt Design
--------------------

The difference between a Hand that works and a Hand that hallucinate is the system prompt. Follow these principles:

1.   -
**Be procedural, not descriptive.** Don't say "you are an invoice processor." Say "Phase 1: Check the input directory for new files. For each file..."

2.   -
**Define phases.** Break the work into numbered phases with concrete steps. The agent follows phases sequentially unless a condition routes it elsewhere.

3.   -
**Include decision trees.** "If the total mismatches by more than 1%, flag for review. If less than 1%, auto-correct and log."

4.   -
**Specify error recovery.** Every phase should have a fallback. Agents that hit errors without recovery instructions will loop or hallucinate.

5.   -
**Set quality gates.** "Do not proceed to Phase 3 until all line items have confidence > 0.9."

SKILL.md Format
---------------

SKILL.md files use standard Markdown with optional YAML frontmatter:

The content is injected into the agent's context window alongside the system prompt. Keep it focused — SKILL.md is for **reference knowledge**, not instructions. Instructions go in the system prompt.

Publishing to FangHub
---------------------

FangHub is OpenFang's marketplace for community Hands. Once your Hand is tested and ready:

Published Hands are verified with SHA256 checksums and scanned for prompt injection attempts before listing. Users install community Hands with:

* * *

Hands represent a paradigm shift in how we think about agents. They're not chatbots. They're not assistants waiting for your next message. They're autonomous specialists that you deploy, configure, and monitor — the same way you'd manage a team of experts. This is what "agents that work for you" actually means.

