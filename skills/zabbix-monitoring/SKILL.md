---
name: zabbix-monitoring
description: Query Zabbix monitoring — check active problems, host metrics, history, triggers, and acknowledge events. Use when asked about alerts, problems, monitoring, metrics, Zabbix, host status, or when investigating webhook alerts.
---

# Zabbix Monitoring

Query Zabbix 7.0 API via `scripts/zabbix_query.py`. See **infrastructure-reference** skill for Zabbix host IDs and full host inventory.

## Commands

Run via `python3 /path/to/scripts/zabbix_query.py <command> [options]`.

```
active-problems [--severity-min N] [--limit N] [--host NAME]  # Current unresolved problems
unacknowledged-problems [--severity-min N] [--limit N]         # Problems not yet handled
hosts                                                           # All monitored hosts with status
host-items <host> [--search TEXT] [--limit N]                  # Monitored metrics for a host
history <itemid> [--type N] [--limit N]                        # Historical values for a metric
triggers <host> [--active-only]                                # Alert conditions for a host
acknowledge <event_id> --message TEXT                          # Mark problem as investigated
problem-details <event_id>                                     # Full context for a specific event
```

## Investigation Patterns

**Webhook alert arrives** -> `problem-details <event_id>` for full context, then `host-items <host>` for current metrics, then `history <itemid>` for trends.

**"Any active problems?"** -> `active-problems` for all, or `active-problems --severity-min 3` for average+.

**"What's happening on this host?"** -> `host-items <host>` to see current metrics, `triggers <host>` for alert conditions.

**"Show me the trend"** -> `host-items <host> --search cpu` to find the itemid, then `history <itemid> --limit 50` for values.

**After investigation** -> `acknowledge <event_id> --message "Investigated: ..."` to mark as handled.

## History Types

| Type | Data |
|------|------|
| 0 | Numeric (float) |
| 1 | Character/string |
| 2 | Log |
| 3 | Numeric (unsigned integer) |
| 4 | Text |

## Environment Variables

Configured in docker-compose:
- `ZABBIX_API_URL` — Zabbix API endpoint
- `ZABBIX_API_TOKEN` — API authentication token

## Dependencies

Stdlib only (no third-party packages).
