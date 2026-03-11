#!/bin/sh
# Zabbix JSON-RPC query helper for OpenFang shell_exec
# Writes params to a temp file to avoid shell metacharacter issues.
#
# Usage: zabbix-query.sh <method> [params_json_file]
#
# If no params file given, uses empty params {}.
# The agent should write JSON params to /tmp/zabbix-params.json first,
# then call this script.
#
# Examples:
#   # Simple: no params needed
#   zabbix-query.sh apiinfo.version
#
#   # With params file:
#   echo '{"output":"extend","recent":true,"limit":5}' > /tmp/zabbix-params.json
#   zabbix-query.sh problem.get /tmp/zabbix-params.json

METHOD="$1"
PARAMS_FILE="${2:-}"

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
