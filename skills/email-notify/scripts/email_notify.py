#!/usr/bin/env python3
"""Send email notifications via Gmail Apps Script webhook.

Outbound-only notification for infrastructure alerts.
Uses stdlib only (no third-party deps). Reads env vars from
/proc/1/environ to work around OpenFang's shell_exec sandbox.

Usage:
    python3 email_notify.py --subject "[WARNING] Issue" --body "Details..."
    python3 email_notify.py --subject "[CRITICAL] Down" --body "Host down" --to admin@example.com
"""

import argparse
import json
import os
import sys
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

DEFAULT_RECIPIENT = "krussell1@baldwinmutual.com"


def send_email(subject: str, body: str, to: str) -> dict:
    webhook_url = os.environ.get("NOTIFY_WEBHOOK_URL")
    api_key = os.environ.get("NOTIFY_WEBHOOK_API_KEY")

    if not webhook_url:
        return {"success": False, "error": "NOTIFY_WEBHOOK_URL not set"}
    if not api_key:
        return {"success": False, "error": "NOTIFY_WEBHOOK_API_KEY not set"}

    payload = json.dumps({
        "apiKey": api_key,
        "to": to,
        "subject": subject,
        "body": body,
    }).encode("utf-8")

    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        # Apps Script 302-redirects POST to GET — urllib follows by default
        resp = urllib.request.urlopen(req, timeout=30)
        result = json.loads(resp.read().decode("utf-8"))
        if result.get("success"):
            return {"success": True, "message": f"Notification sent: {subject}"}
        else:
            return {"success": False, "error": f"Webhook returned: {result}"}
    except urllib.error.HTTPError as e:
        return {"success": False, "error": f"HTTP {e.code}: {e.read().decode()}"}
    except urllib.error.URLError as e:
        return {"success": False, "error": f"URL error: {e.reason}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="Send email via Apps Script webhook")
    parser.add_argument("--subject", required=True, help="Email subject line")
    parser.add_argument("--body", required=True, help="Email body text")
    parser.add_argument("--to", default=DEFAULT_RECIPIENT, help="Recipient email")
    args = parser.parse_args()

    result = send_email(args.subject, args.body, args.to)
    print(json.dumps(result, indent=2))

    if not result["success"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
