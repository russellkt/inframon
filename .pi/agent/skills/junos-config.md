# junos-config

Query Juniper switch configuration and status.

## Tools

### get-interface-status
Get interface status and statistics.

**Parameters:**
- `host` - Switch hostname (ex2300, ex3400)
- `interface` (optional) - Specific interface (ge-0/0/0)

**Returns:** Interface list with admin/operational status, MTU, errors, traffic

### get-bgp-status
Get BGP session status.

**Parameters:**
- `host` - Switch hostname

**Returns:** BGP neighbors, session state, routes

### get-route-table
Get routing table.

**Parameters:**
- `host` - Switch hostname
- `prefix` (optional) - Filter by prefix

**Returns:** Routes with next-hop, metric, age

### get-configuration
Get running configuration.

**Parameters:**
- `host` - Switch hostname
- `section` (optional) - Config section to retrieve

**Returns:** Configuration text or section
