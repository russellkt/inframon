---
name: proxmox-monitoring
description: Monitor Proxmox VE cluster — check cluster health, node status, VM/container inventory, storage, disks, and networking. Use when asked about Proxmox, VMs, containers, nodes, cluster status, storage capacity, or hypervisor health.
---

# Proxmox Cluster Monitoring

Query Proxmox VE REST API via `scripts/proxmox_query.py`. See **infrastructure-reference** skill for cluster node inventory.

## Commands

Run via `python3 /path/to/scripts/proxmox_query.py <command> [options]`.

```
cluster-status                          # Cluster health, quorum, node membership
nodes                                   # All nodes with CPU/memory/disk usage
node-status <node>                      # Detailed node info (CPU, memory, kernel, load)
vms [--node NAME] [--type qemu|lxc]     # VMs and containers with status
storage                                 # Storage status across cluster
node-disks <node>                       # Physical disk info per node
node-networks <node>                    # Network interface config per node
```

## Investigation Patterns

**"Is the cluster healthy?"** -> `cluster-status` for quorum and node membership, then `nodes` for resource usage.

**"What's running on pve-r720?"** -> `vms --node pve-r720` for all VMs/CTs on that node.

**"Is storage getting full?"** -> `storage` for all pools, look at usage percentages.

**"Node seems slow"** -> `node-status <node>` for CPU, memory, load averages.

**"What disks are in this node?"** -> `node-disks <node>` for physical disk inventory.

**"Network config check"** -> `node-networks <node>` for bridge, bond, VLAN interfaces.

## Environment Variables

Configured in docker-compose:
- `PVE_API_URL` — Proxmox VE API base URL (e.g. https://10.10.1.14:8006)
- `PVE_API_TOKEN_ID` — API token ID (e.g. inframon@pve!monitoring)
- `PVE_API_TOKEN_SECRET` — API token secret

## Dependencies

Stdlib only (no third-party packages).
