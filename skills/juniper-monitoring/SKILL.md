---
name: juniper-monitoring
description: Monitor Juniper EX switches — check interface status, alarms, LLDP neighbors, environment health, MAC table, VLANs, and routing. Use when asked about switches, interfaces, ports, link status, LLDP, VLANs, MAC addresses, Juniper, EX3400, EX2300, or network connectivity.
---

# Juniper Switch Monitoring

Query Juniper EX switches via REST API using `scripts/juniper_query.py`.

## Switches

| Name | IP | Model | Access |
|------|-----|-------|--------|
| ex3400 / bmic-ex3400-1 | 10.10.1.10 | Juniper EX3400-48P | REST API port 3000 |
| ex2300 / bmic-ex2300-1 | 10.10.1.9 | Juniper EX2300-C-12P | REST API port 3000 |

## Commands

Run via `python3 /path/to/scripts/juniper_query.py <command> <host> [options]`.

Host can be an IP or alias: `ex3400`, `ex2300`, `bmic-ex3400-1`, `bmic-ex2300-1`.

```
interfaces <host> [--name IF] [--terse]  # Interface status, traffic stats, errors
alarms <host>                            # Active alarms with severity
lldp-neighbors <host>                    # Physical connectivity discovery
environment <host>                       # Temperature, fan status, PSU health
mac-table <host>                         # MAC address table for device location
chassis-inventory <host>                 # Hardware models, serial numbers
route-summary <host>                     # Routing table summary
software-info <host>                     # Junos version info
vlans <host>                             # VLAN config with member interfaces
```

## Investigation Patterns

**"Is a port down?"** -> `interfaces <host> --name ge-0/0/3` for specific port, or `interfaces <host> --terse` for all ports.

**"Any switch alarms?"** -> `alarms <host>` for active alarms. Check both switches.

**"What's connected to this port?"** -> `lldp-neighbors <host>` for physical topology.

**"Where is device X?"** -> `mac-table <host>` to find which port a MAC address is on.

**"Is the switch overheating?"** -> `environment <host>` for temperatures, fans, PSUs.

**"What VLANs are configured?"** -> `vlans <host>` for VLAN names, IDs, and members.

## Environment Variables

Configured in docker-compose:
- `JUNIPER_USER` — Switch username (e.g. inframon)
- `JUNIPER_PASSWORD` — Switch password

## Dependencies

Stdlib only (no third-party packages).
