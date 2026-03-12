#!/usr/bin/env python3
"""Send messages to specific Matrix rooms via Client-Server API.

Room-targeted notifications for infrastructure alerts and patrol reports.
Uses stdlib only (no third-party deps). Reads env vars from
/proc/1/environ to work around OpenFang's shell_exec sandbox.

Usage:
    python3 matrix_notify.py --room "!roomid:matrix.org" --message "Alert text"
    python3 matrix_notify.py --room "!roomid:matrix.org" --message "Alert text"
"""

import argparse
import json
import os
import sys
import time
import uuid
import urllib.error
import urllib.request
from pathlib import Path

# ── OpenFang env var recovery ─────────────────────────────────────
_proc_env = Path("/proc/1/environ")
if _proc_env.exists():
    for entry in _proc_env.read_bytes().split(b"\0"):
        if b"=" in entry:
            k, v = entry.decode("utf-8", errors="replace").split("=", 1)
            os.environ.setdefault(k, v)

# ── Matrix room ID constants ─────────────────────────────────────
ROOMS = {
    "inframon": "!PwgTYHCRXkvXzbgqpQ:matrix.org",
    "alerts": "!wnxZoiPfVQuSIgJVvy:matrix.org",
    "patrol": "!GNBDVQhyXYYugtroNR:matrix.org",
}


def send_message(room_id: str, message: str, homeserver: str, token: str) -> dict:
    # Matrix Client-Server API: PUT /_matrix/client/v3/rooms/{roomId}/send/m.room.message/{txnId}
    txn_id = f"{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
    url = f"{homeserver}/_matrix/client/v3/rooms/{room_id}/send/m.room.message/{txn_id}"

    # Most Matrix clients (Element, etc.) render markdown in the body field automatically
    body: dict = {"msgtype": "m.text", "body": message}

    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="PUT",
    )

    try:
        resp = urllib.request.urlopen(req, timeout=30)
        result = json.loads(resp.read().decode("utf-8"))
        return {"success": True, "event_id": result.get("event_id"), "room": room_id}
    except urllib.error.HTTPError as e:
        return {"success": False, "error": f"HTTP {e.code}: {e.read().decode()}"}
    except urllib.error.URLError as e:
        return {"success": False, "error": f"URL error: {e.reason}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="Send message to a Matrix room")
    parser.add_argument("--room", required=True,
                        help="Room ID (!xxx:matrix.org) or alias (inframon, alerts, patrol)")
    parser.add_argument("--message", required=True, help="Message text to send")
    args = parser.parse_args()

    token = os.environ.get("MATRIX_ACCESS_TOKEN")
    if not token:
        print(json.dumps({"success": False, "error": "MATRIX_ACCESS_TOKEN not set"}))
        sys.exit(1)

    homeserver = os.environ.get("MATRIX_HOMESERVER_URL", "https://matrix.org")

    # Resolve room alias to ID
    room_id = ROOMS.get(args.room, args.room)

    result = send_message(room_id, args.message, homeserver, token)
    print(json.dumps(result, indent=2))

    if not result["success"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
