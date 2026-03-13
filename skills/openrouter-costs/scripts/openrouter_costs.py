#!/usr/bin/env python3
"""Query OpenRouter API usage and costs.

Usage:
    python3 openrouter_costs.py summary
    python3 openrouter_costs.py daily
    python3 openrouter_costs.py weekly
    python3 openrouter_costs.py monthly
"""

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

# OpenFang env var recovery
_proc_env = Path("/proc/1/environ")
if _proc_env.exists():
    for entry in _proc_env.read_bytes().split(b"\0"):
        if b"=" in entry:
            k, v = entry.decode("utf-8", errors="replace").split("=", 1)
            os.environ.setdefault(k, v)

API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
BASE_URL = "https://openrouter.ai/api/v1"


def api_get(path):
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        headers={"Authorization": f"Bearer {API_KEY}"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def cmd_summary(_args):
    data = api_get("/auth/key")["data"]
    result = {
        "daily_usd":   round(data["usage_daily"], 4),
        "weekly_usd":  round(data["usage_weekly"], 4),
        "monthly_usd": round(data["usage_monthly"], 4),
        "total_usd":   round(data["usage"], 4),
        "byok_daily_usd":   round(data["byok_usage_daily"], 4),
        "byok_weekly_usd":  round(data["byok_usage_weekly"], 4),
        "byok_monthly_usd": round(data["byok_usage_monthly"], 4),
        "limit": data["limit"],
        "limit_remaining": data["limit_remaining"],
    }
    print(json.dumps(result, indent=2))


COMMANDS = {"summary": cmd_summary, "daily": cmd_summary, "weekly": cmd_summary, "monthly": cmd_summary}

if __name__ == "__main__":
    if not API_KEY:
        print(json.dumps({"error": "OPENROUTER_API_KEY not set"}))
        sys.exit(1)

    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=COMMANDS.keys())
    args = parser.parse_args()
    COMMANDS[args.command](args)
