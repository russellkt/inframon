#!/bin/sh
# Zabbix JSON-RPC query helper for OpenFang shell_exec
# Reads env from /proc/1/environ since sandbox strips env vars.
#
# Usage: zabbix-query.sh <method> [params_json_file]

METHOD="$1"
PARAMS_FILE="${2:-}"

# Read env vars from container's PID 1 (sandbox strips them)
if [ -z "$ZABBIX_API_URL" ] && [ -f /proc/1/environ ]; then
    ZABBIX_API_URL=$(tr '\0' '\n' < /proc/1/environ | grep '^ZABBIX_API_URL=' | cut -d= -f2-)
    ZABBIX_API_TOKEN=$(tr '\0' '\n' < /proc/1/environ | grep '^ZABBIX_API_TOKEN=' | cut -d= -f2-)
    export ZABBIX_API_URL ZABBIX_API_TOKEN
fi

if [ -n "$PARAMS_FILE" ] && [ -f "$PARAMS_FILE" ]; then
    PARAMS=$(cat "$PARAMS_FILE")
else
    PARAMS='{}'
fi

printf '{"jsonrpc":"2.0","method":"%s","id":1,"params":%s}' "$METHOD" "$PARAMS" > /tmp/zabbix-request.json

curl -s -X POST "$ZABBIX_API_URL" \
  -H "Content-Type: application/json-rpc" \
  -H "Authorization: Bearer $ZABBIX_API_TOKEN" \
  -d @/tmp/zabbix-request.json

rm -f /tmp/zabbix-request.json
