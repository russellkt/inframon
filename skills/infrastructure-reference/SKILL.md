---
name: infrastructure-reference
description: Canonical infrastructure inventory — all hosts, IPs, hardware specs, VLANs, Zabbix host IDs, PBS instances, and network topology. Referenced by all other monitoring skills. Always loaded for infrastructure questions.
trigger_words:
  - infrastructure
  - inventory
  - host
  - ip address
  - network
  - vlan
  - topology
  - what hosts
  - where is
---

# BMIC Infrastructure Reference

Canonical source of truth for all infrastructure hosts, IPs, and topology. Other skills reference this rather than duplicating.

## VLAN 1010 Host Inventory (10.10.1.0/24)

| IP | Hostname | Type | Notes |
|---|---|---|---|
| 10.10.1.1 | SonicWall TZ370 | Gateway/Firewall | VLAN 1010 gateway |
| 10.10.1.6 | BMISHARE | LXC (CT 102, pve-p520) | File server, 3.7TB /storage |
| 10.10.1.7 | icx7150-c12p-1 | Network switch | Brocade ICX7150-C12P, 12x 1G PoE + 2x 10G SFP+ |
| 10.10.1.9 | bmic-ex2300-1 | Network switch | Juniper EX2300-C-12P, REST API port 3000 |
| 10.10.1.10 | bmic-ex3400-1 | Network switch | Juniper EX3400-48P, REST API port 3000 |
| 10.10.1.14 | pve-r720 | Proxmox node | Dell R720, 16c/32t, 168 GB RAM |
| 10.10.1.77 | pve-z2 | Proxmox node | HP Z2 G4, 8c/16t, 64 GB RAM, 2x 10G SFP+ + 2x 10G RJ45 |
| 10.10.1.78 | truenas-ts140 | TrueNAS SCALE 25.04 | Xeon E3-1225 v3, 4c, pool: tank (mirror 2x14TB) |
| 10.10.1.79 | pve-r620 | Proxmox node | Dell R620, 12c/24t, 128 GB RAM |
| 10.10.1.80 | pve-p520 | Proxmox node | HP P520, 8c/16t, 128 GB RAM |
| 10.10.1.92 | pve5820gpu | Proxmox node | GPU workstation, 32 GB RAM |
| 10.10.1.135 | win10-kr | VM (107, pve-z2) | Windows 10 |
| 10.10.1.141 | PBS primary | LXC (CT 851, pve-r720) | PBS, Web UI https://10.10.1.141:8007 |
| 10.10.1.142 | zabbix | VM (120, pve-z2) | Zabbix 7.0 monitoring |
| 10.10.1.145 | pbs-ts140 | Incus LXC (TrueNAS) | PBS, Web UI https://10.10.1.145:8007 |
| 10.10.1.148 | Mac Mini | Workstation | Admin machine, macOS |
| 10.10.1.149 | ubuntu-llm-server | VM (432, pve5820gpu) | LLM inference server |
| 10.10.1.200 | bmi-icx6450-48 | Network switch | Brocade ICX6450-48 |
| 10.10.1.254 | bmic-icx6610-1 | Network switch | Brocade ICX6610, 10G SFP+ uplinks |

### Offsite / Remote

| IP | Hostname | Type | Notes |
|---|---|---|---|
| 100.100.58.6 | pbs-offsite | LXC (CT 821, pve-705mini) | PBS offsite, ZFS mirror 2x6TB |
| 10.10.1.146 | pve-705mini | Proxmox node | AOOSTAR WTR PRO, offsite PBS host |

## Zabbix Host IDs

| hostid | host | IP | Type |
|--------|------|----|------|
| 10084 | Zabbix server | 127.0.0.1 | Monitoring |
| 10585 | icx6610 | 192.168.2.202 | Switch (Brocade) |
| 10589 | sonic-tz370 | 192.168.2.2 | Firewall |
| 10590 | pve-z2 | 10.10.1.77 | Proxmox hypervisor |
| 10591 | pve-p520 | 10.10.1.80 | Proxmox hypervisor |
| 10593 | pdu-pro | 192.168.2.17 | PDU |
| 10594 | ex2300 | 10.10.1.9 | Switch (Juniper EX2300) |
| 10595 | ex3400 | 10.10.1.10 | Switch (Juniper EX3400) |
| 10596 | pve-r720 | 10.10.1.14 | Proxmox hypervisor |
| 10597 | pve5820gpu | 10.10.1.92 | Proxmox hypervisor |
| 10598 | pve-r620 | 10.10.1.79 | Proxmox hypervisor |

## PBS Instances

| Name | IP | Host | Storage |
|------|-----|------|---------|
| primary | 10.10.1.141 | pve-r720 (CT 851) | ZFS `spinners` |
| ts140 | 10.10.1.145 | truenas-ts140 (Incus LXC) | ZFS `tank` |
| offsite | 100.100.58.6 | pve-705mini (CT 821) | ZFS mirror 2x6TB |

## Network Topology

- **Gateway:** SonicWall TZ370 (10.10.1.1)
- **Switches:** Juniper EX3400 (.10), EX2300 (.9), Brocade ICX6610 (.254), ICX7150 (.7), ICX6450 (.200), QNAP QSW-308-1C (unmanaged, no IP)
- **10G Fabric:** QNAP QSW-308 bridges pve5820gpu (SFP+) and pve-z2 (10G RJ45); uplinks to ICX7150 1/3/1 SFP+
- **VLAN 1010:** Server/infrastructure VLAN; nodes tag VLAN 1010 (trunk ports on switches)
- **DHCP:** SonicWall

## VLANs

| VLAN | Name | Subnet | Purpose |
|------|------|--------|---------|
| 1 | DEFAULT-VLAN | 192.168.2.0/24 | Corporate LAN |
| 10 | VOIP | — | IP phones |
| 1010 | SERVE | 10.10.1.0/24 | Infrastructure |

## Severity Levels (Zabbix)

| Value | Label | Action |
|-------|-------|--------|
| 0 | Not classified | Ignore |
| 1 | Information | Log only |
| 2 | Warning | Monitor, notify if persistent |
| 3 | Average | Investigate, notify |
| 4 | High | Notify immediately, investigate urgently |
| 5 | Disaster | Notify immediately, escalate |

## Matrix Rooms

| Room | Alias | Room ID | Purpose |
|------|-------|---------|---------|
| #inframon | `inframon` | `!PwgTYHCRXkvXzbgqpQ:matrix.org` | Interactive chat |
| #inframon-alerts | `alerts` | `!wnxZoiPfVQuSIgJVvy:matrix.org` | Alert investigations, critical findings |
| #inframon-patrol | `patrol` | `!GNBDVQhyXYYugtroNR:matrix.org` | Nightly sweep reports |

Bot account: `@inframon:matrix.org` on `matrix.org` homeserver.
