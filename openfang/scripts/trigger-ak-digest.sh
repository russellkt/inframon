#!/bin/bash
# Trigger the ak-digest agent via OpenFang API.
# Add to crontab on the Docker host: 0 9 * * 0 /opt/inframon/openfang/scripts/trigger-ak-digest.sh

DIGEST_ID=$(curl -sf http://localhost:4200/api/agents | python3 -c "import sys,json; agents=json.load(sys.stdin); [print(a['id']) for a in agents if a['name']=='ak-digest']" 2>/dev/null)
if [ -z "$DIGEST_ID" ]; then
    echo "$(date): ak-digest agent not found" >> /tmp/ak-digest-cron.log
    exit 1
fi

# Start a fresh session so each digest run has a clean context
curl -sf -X POST "http://localhost:4200/api/agents/$DIGEST_ID/session/reset" >> /tmp/ak-digest-cron.log 2>&1

curl -sf -X POST "http://localhost:4200/api/agents/$DIGEST_ID/message" \
    -H "Content-Type: application/json" \
    -d '{"message": "Run weekly knowledge digest. Analyze all projects, find patterns and decisions, post report to Matrix."}' \
    >> /tmp/ak-digest-cron.log 2>&1 || echo "$(date): curl failed with exit code $?" >> /tmp/ak-digest-cron.log
