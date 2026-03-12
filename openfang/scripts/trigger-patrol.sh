#!/bin/bash
# Trigger the inframon-patrol agent via OpenFang API.
# Add to crontab on the Docker host: 0 2 * * * /path/to/trigger-patrol.sh

PATROL_ID=$(curl -sf http://localhost:4200/api/agents | python3 -c "import sys,json; agents=json.load(sys.stdin); [print(a['id']) for a in agents if a['name']=='inframon-patrol']" 2>/dev/null)
if [ -z "$PATROL_ID" ]; then
    echo "$(date): inframon-patrol agent not found" >> /tmp/patrol-cron.log
    exit 1
fi

# Start a fresh session so each patrol run has a clean context
curl -sf -X POST "http://localhost:4200/api/agents/$PATROL_ID/session/reset" >> /tmp/patrol-cron.log 2>&1

curl -sf -X POST "http://localhost:4200/api/agents/$PATROL_ID/message" \
    -H "Content-Type: application/json" \
    -d '{"message": "Run nightly patrol. Check all infrastructure and post report."}' \
    >> /tmp/patrol-cron.log 2>&1 || echo "$(date): curl failed with exit code $?" >> /tmp/patrol-cron.log
