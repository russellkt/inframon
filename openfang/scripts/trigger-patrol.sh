#!/bin/bash
# Trigger the inframon-patrol agent via OpenFang API.
# Add to crontab on the Docker host: 0 2 * * * /path/to/trigger-patrol.sh
curl -sf -X POST http://localhost:4200/api/agents/inframon-patrol/message \
    -H "Content-Type: application/json" \
    -d '{"message": "Run nightly patrol. Check all infrastructure and post report."}' \
    >> /tmp/patrol-cron.log 2>&1
