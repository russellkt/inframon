#!/bin/bash
# scripts/setup-ak-openfang.sh
# Register ak-maintenance workflow, cron, and digest trigger with OpenFang.
# Run after EVERY container recreate — workflows are NOT persisted in the DB
# across rebuilds (agents and cron/triggers are, workflows are not).
# Usage: ./scripts/setup-ak-openfang.sh [host]
# Default host: 10.10.1.127:4200

set -euo pipefail

HOST="${1:-10.10.1.127:4200}"
BASE="http://${HOST}"

echo "[setup-ak] Using OpenFang at $BASE"

# 1. Spawn ak agents (if not already in DB)
echo "[setup-ak] Spawning ak agents..."
for agent in ak-enrich ak-tidy ak-snapshot ak-digest; do
    curl -sf -X POST "$BASE/api/agents" \
        -H "Content-Type: application/json" \
        -d "{\"manifest_path\": \"/data/agents/${agent}/agent.toml\"}" \
        && echo "[setup-ak] Spawned $agent" \
        || echo "[setup-ak] WARN: $agent may already exist"
done

# 2. Register ak-maintenance workflow
echo "[setup-ak] Registering ak-maintenance workflow..."
WORKFLOW_RESP=$(curl -sf -X POST "$BASE/api/workflows" \
    -H "Content-Type: application/json" \
    -d @openfang/workflows/ak-maintenance.json)
WORKFLOW_ID=$(echo "$WORKFLOW_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('workflow_id') or d.get('id'))")
echo "[setup-ak] Workflow ID: $WORKFLOW_ID"

# 3. Get ak-snapshot agent ID (for cron job ownership)
SNAPSHOT_ID=$(curl -sf "$BASE/api/agents" | python3 -c "
import sys, json
agents = json.load(sys.stdin)
for a in agents:
    if a.get('name') == 'ak-snapshot':
        print(a['id'])
        break
")
echo "[setup-ak] ak-snapshot agent ID: $SNAPSHOT_ID"

# 4. Register cron job: run ak-maintenance workflow every 6 hours
echo "[setup-ak] Registering 6-hour maintenance cron..."
curl -sf -X POST "$BASE/api/cron" \
    -H "Content-Type: application/json" \
    -d "{
        \"agent_id\": \"$SNAPSHOT_ID\",
        \"name\": \"ak-maintenance-6h\",
        \"enabled\": true,
        \"schedule\": {\"kind\": \"cron\", \"expr\": \"0 */6 * * *\"},
        \"action\": {\"kind\": \"workflow_run\", \"workflow_id\": \"$WORKFLOW_ID\"},
        \"delivery\": {\"kind\": \"none\"}
    }"
echo "[setup-ak] Cron registered."

# 5. Get ak-digest agent ID
DIGEST_ID=$(curl -sf "$BASE/api/agents" | python3 -c "
import sys, json
agents = json.load(sys.stdin)
for a in agents:
    if a.get('name') == 'ak-digest':
        print(a['id'])
        break
")
echo "[setup-ak] ak-digest agent ID: $DIGEST_ID"

# 6. Register ContentMatch trigger: fire ak-digest when workflow completes
echo "[setup-ak] Registering ak-digest ContentMatch trigger..."
curl -sf -X POST "$BASE/api/triggers" \
    -H "Content-Type: application/json" \
    -d "{
        \"agent_id\": \"$DIGEST_ID\",
        \"pattern\": {\"type\": \"content_match\", \"substring\": \"ak-maintenance complete\"},
        \"prompt_template\": \"The ak-maintenance workflow just completed. Run your cross-project digest now.\",
        \"max_fires\": 0
    }"
echo "[setup-ak] Trigger registered."

echo "[setup-ak] Done. Verify with:"
echo "  curl -s $BASE/api/workflows | python3 -m json.tool"
echo "  curl -s $BASE/api/cron | python3 -m json.tool"
echo "  curl -s $BASE/api/triggers | python3 -m json.tool"
