# zabbix-ops

Query Zabbix API for infrastructure monitoring data.

## Tools

### query-problems
Query unacknowledged problems from Zabbix.

**Parameters:**
- `host` (optional) - Filter by hostname
- `severity` (optional) - Minimum severity (Information, Warning, Average, High, Disaster)
- `limit` - Results limit (default: 20)

**Returns:** Array of problem objects with ID, host, description, severity, created timestamp

### get-history
Get historical values for a metric.

**Parameters:**
- `item_id` - Zabbix item ID
- `value_type` - Type (0=float, 1=char, 2=log, 3=uint64, 4=text)
- `time_from` - Start timestamp
- `time_till` - End timestamp
- `limit` - Max results (default: 100)

**Returns:** Array of history points with value and timestamp

### acknowledge-problem
Acknowledge a Zabbix problem (stop further alerts).

**Parameters:**
- `event_ids` - Array of event IDs to acknowledge
- `message` - Acknowledgment message

**Returns:** Success/failure status
