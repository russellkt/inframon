# OpenFang Upstream Issues & PRs Needed

Issues discovered in production use. File at https://github.com/RightNow-AI/openfang/issues.

---

## Bugs

### `openfang cron create` reports "Failed: ?" on success
**Discovered:** 2026-03-13
**Symptom:** CLI prints `✘ Failed: ?` after `cron create`, but the API returns 201 and the job is created. Caused us to create 3 duplicate crons before we caught it by watching server logs.
**Workaround:** Always verify with `openfang cron list` after creating a cron.
**Fix needed:** CLI should parse the 201 response and print `✔ Created`.

---

### Local provider URLs hardcoded to localhost; `OLLAMA_BASE_URL` ignored
**Discovered:** ~2026-03-11
**Symptom:** All local providers (Ollama, vLLM, LMStudio, Lemonade) are hardcoded to `localhost:<port>`. The `OLLAMA_BASE_URL` env var is silently ignored. Embeddings also hardcoded — can't use a remote Ollama for embeddings.
**Workaround:** Can't use a remote Ollama instance as a local provider without a socat/proxy sidecar. We currently proxy via the OpenAI-compatible provider.
**Fix needed:** Respect `OLLAMA_BASE_URL` (and equivalent vars for other providers) to allow remote local-model servers.

---

### Shell sandbox strips environment variables from subprocesses
**Discovered:** ~2026-03-11
**Symptom:** `shell_exec` subprocesses inherit no env vars from the container, even with `exec_policy = "full"`. MCP server subprocesses are also affected.
**Workaround:** Every skill script reads env from `/proc/1/environ` at import time. Only works on Linux — fragile.
**Fix needed:** Subprocess env should inherit from the daemon process, especially when `exec_policy = "full"`.

---

## Feature Requests

### Workflows should persist across restarts (load from directory on startup)
**Discovered:** 2026-03-13
**Symptom:** Workflows are pure in-memory (`Arc<RwLock<HashMap>>`). Every container restart loses all workflow definitions. Cron jobs correctly persist in SQLite — workflows should too, or OpenFang should load `*.json` files from a configured workflows directory on startup.
**Workaround:** `workflow-init` sidecar service in docker-compose that re-POSTs all workflow JSON files after healthcheck passes.
**Fix needed:** Either persist workflows in SQLite alongside crons, or auto-load from `$OPENFANG_HOME/workflows/` on daemon start.

---

### New agents require manual `spawn` to register in DB
**Discovered:** ~2026-03-12
**Symptom:** Agents defined in `/data/agents/<name>/agent.toml` are not auto-discovered on startup if they've never been spawned before. Must run `openfang agent spawn /data/agents/<name>/agent.toml` once manually.
**Workaround:** Manual spawn after first deploy of a new agent.
**Fix needed:** Auto-discover and register agents from the agents directory on startup (or at minimum, a startup flag/config option to do so).

---

### `GET /api/metrics` lacks useful observability data
**Discovered:** ~2026-03-13
**Symptom:** Prometheus endpoint only exposes basic counters (uptime, agent count, token totals, tool calls, panics, restarts). No latency histograms, per-request error rates, or cost breakdown by agent.
**Fix needed:** Add `openfang_llm_latency_seconds` histogram, per-agent cost gauge, error rate counter, and queue depth for `task_queue`.
