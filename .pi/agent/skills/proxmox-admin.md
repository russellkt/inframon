# proxmox-admin

Query Proxmox API for infrastructure status.

## Tools

### get-cluster-status
Get overall cluster health.

**Returns:** Cluster quorum, node status, shared resources

### get-node-status
Get status of a specific node.

**Parameters:**
- `node` - Node name (pve-r720, pve-p520, pve5820gpu, pve-z2)

**Returns:** CPU, memory, disk usage, uptime, services status

### get-storage-status
Get storage pool status.

**Returns:** Storage pools with free/used space, utilization percentage

### list-vms
List running/stopped VMs.

**Parameters:**
- `node` (optional) - Filter by node

**Returns:** VM list with ID, name, status, uptime, resources

### get-lxc-status
Get LXC container status.

**Parameters:**
- `container_id` - Container ID

**Returns:** Container status, resource usage
