#!/bin/sh
# Entrypoint: refresh Matrix token if stale, then start OpenFang.
#
# Requires env vars:
#   MATRIX_ACCESS_TOKEN  — current token (may be stale)
#   MATRIX_PASSWORD      — used to refresh if token is invalid
#   MATRIX_HOMESERVER_URL (optional, defaults to https://matrix.org)
#
# On a valid token: starts OpenFang unchanged.
# On a 401:        logs in with device_id=INFRAMON_BOT, writes new token
#                  to /data/data/matrix_token (persisted volume), exports
#                  it into the process environment, then starts OpenFang.

HOMESERVER="${MATRIX_HOMESERVER_URL:-https://matrix.org}"
TOKEN_FILE="/data/data/matrix_token"

# If a previously-refreshed token is persisted, prefer it over the env var
if [ -f "$TOKEN_FILE" ]; then
    MATRIX_ACCESS_TOKEN="$(cat $TOKEN_FILE)"
    export MATRIX_ACCESS_TOKEN
fi

# Check if current token is valid
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer ${MATRIX_ACCESS_TOKEN}" \
    "${HOMESERVER}/_matrix/client/v3/account/whoami")

if [ "$HTTP_STATUS" = "200" ]; then
    echo "[entrypoint] Matrix token OK"
else
    echo "[entrypoint] Matrix token invalid (${HTTP_STATUS}), refreshing..."

    if [ -z "$MATRIX_PASSWORD" ]; then
        echo "[entrypoint] ERROR: MATRIX_PASSWORD not set, cannot refresh token"
        exit 1
    fi

    RESPONSE=$(curl -s -X POST "${HOMESERVER}/_matrix/client/v3/login" \
        -H "Content-Type: application/json" \
        -d "{\"type\":\"m.login.password\",\"identifier\":{\"type\":\"m.id.user\",\"user\":\"inframon\"},\"password\":\"${MATRIX_PASSWORD}\",\"device_id\":\"INFRAMON_BOT\",\"initial_device_display_name\":\"inframon-openfang\"}")

    NEW_TOKEN=$(echo "$RESPONSE" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

    if [ -z "$NEW_TOKEN" ]; then
        echo "[entrypoint] ERROR: Failed to get new token. Response: $RESPONSE"
        exit 1
    fi

    echo "[entrypoint] Token refreshed successfully"
    echo "$NEW_TOKEN" > "$TOKEN_FILE"
    MATRIX_ACCESS_TOKEN="$NEW_TOKEN"
    export MATRIX_ACCESS_TOKEN
fi

exec openfang start
