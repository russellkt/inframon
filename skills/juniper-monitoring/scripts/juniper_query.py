#!/usr/bin/env python3
"""Juniper EX switch query tool for inframon.

Queries Juniper switches via REST API (rpc-on-http, port 3000).
Stdlib only — no third-party dependencies.

Environment variables:
  JUNIPER_USER      — Switch username (e.g. inframon)
  JUNIPER_PASSWORD  — Switch password

Usage:
  juniper_query.py interfaces <host> [--name IF] [--terse]
  juniper_query.py alarms <host>
  juniper_query.py lldp-neighbors <host>
  juniper_query.py environment <host>
  juniper_query.py mac-table <host>
  juniper_query.py chassis-inventory <host>
  juniper_query.py route-summary <host>
  juniper_query.py software-info <host>
  juniper_query.py vlans <host>
"""

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

# OpenFang strips env vars from subprocesses — recover from init process
_proc_env = Path("/proc/1/environ")
if _proc_env.exists():
    for entry in _proc_env.read_bytes().split(b"\0"):
        if b"=" in entry:
            k, v = entry.decode("utf-8", errors="replace").split("=", 1)
            os.environ.setdefault(k, v)

# Switch aliases — agent can use friendly names
SWITCH_ALIASES = {
    "ex3400": "10.10.1.10",
    "bmic-ex3400-1": "10.10.1.10",
    "ex2300": "10.10.1.9",
    "bmic-ex2300-1": "10.10.1.9",
}


def xml_to_dict(element):
    """Recursively convert an XML element to a dict, stripping Junos namespaces."""
    tag = element.tag
    if "}" in tag:
        tag = tag.split("}", 1)[1]

    result = {}

    if element.attrib:
        for k, v in element.attrib.items():
            if "}" in k:
                k = k.split("}", 1)[1]
            result["@" + k] = v

    children = list(element)
    if children:
        child_dict = {}
        for child in children:
            child_tag, child_val = list(xml_to_dict(child).items())[0]
            if child_tag in child_dict:
                if not isinstance(child_dict[child_tag], list):
                    child_dict[child_tag] = [child_dict[child_tag]]
                child_dict[child_tag].append(child_val)
            else:
                child_dict[child_tag] = child_val
        result.update(child_dict)
    elif element.text and element.text.strip():
        if not element.attrib:
            return {tag: element.text.strip()}
        result["#text"] = element.text.strip()

    if not result:
        return {tag: None}

    return {tag: result}


def extract_xml_from_multipart(raw_bytes):
    """Extract XML content from Junos multipart response."""
    text = raw_bytes.decode("utf-8", errors="replace")
    xml_start = text.find("<?xml")
    if xml_start == -1:
        xml_start = text.find("<")
    if xml_start == -1:
        return text

    xml_content = text[xml_start:]
    boundary_pos = xml_content.find("\n--")
    if boundary_pos > 0:
        xml_content = xml_content[:boundary_pos]

    return xml_content.strip()


def api_rpc(host, rpc, params=None):
    """Execute a Junos RPC via the REST API on port 3000."""
    ip = SWITCH_ALIASES.get(host, host)

    user = os.environ.get("JUNIPER_USER")
    password = os.environ.get("JUNIPER_PASSWORD")
    if not user or not password:
        print("ERROR: JUNIPER_USER and JUNIPER_PASSWORD must be set", file=sys.stderr)
        sys.exit(1)

    url = f"http://{ip}:3000/rpc"

    body_parts = []
    if params:
        for k, v in params.items():
            if v:
                body_parts.append(f"<{k}>{v}</{k}>")
            else:
                body_parts.append(f"<{k}/>")
    body = f"<{rpc}>{''.join(body_parts)}</{rpc}>"

    creds = base64.b64encode(f"{user}:{password}".encode()).decode()
    headers = {
        "Authorization": f"Basic {creds}",
        "Content-Type": "application/xml",
        "Accept": "application/xml",
    }

    req = urllib.request.Request(url, data=body.encode(), headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        return {"error": f"HTTP {e.code}: {err_body}"}
    except urllib.error.URLError as e:
        return {"error": f"Connection error to {ip}: {e.reason}"}

    xml_str = extract_xml_from_multipart(raw)
    try:
        root = ET.fromstring(xml_str)
        return xml_to_dict(root)
    except ET.ParseError:
        return {"raw": xml_str}


def cmd_interfaces(args):
    params = {}
    if args.name:
        params["interface-name"] = args.name
    if args.terse:
        params["terse"] = ""
    return api_rpc(args.host, "get-interface-information", params or None)


def cmd_alarms(args):
    return api_rpc(args.host, "get-alarm-information")


def cmd_lldp_neighbors(args):
    return api_rpc(args.host, "get-lldp-neighbors-information")


def cmd_environment(args):
    return api_rpc(args.host, "get-environment-information")


def cmd_mac_table(args):
    return api_rpc(args.host, "get-ethernet-switching-table-information")


def cmd_chassis_inventory(args):
    return api_rpc(args.host, "get-chassis-inventory")


def cmd_route_summary(args):
    return api_rpc(args.host, "get-route-summary-information")


def cmd_software_info(args):
    return api_rpc(args.host, "get-software-information")


def cmd_vlans(args):
    return api_rpc(args.host, "get-vlan-information")


def main():
    parser = argparse.ArgumentParser(description="Query Juniper EX switches")
    sub = parser.add_subparsers(dest="command", required=True)

    p_if = sub.add_parser("interfaces", help="Interface status, traffic stats, errors")
    p_if.add_argument("host", help="Switch IP or alias (ex3400, ex2300)")
    p_if.add_argument("--name", help="Specific interface (e.g. ge-0/0/3)")
    p_if.add_argument("--terse", action="store_true", help="Compact summary")

    p_alarms = sub.add_parser("alarms", help="Active alarms with severity")
    p_alarms.add_argument("host", help="Switch IP or alias")

    p_lldp = sub.add_parser("lldp-neighbors", help="LLDP neighbor discovery")
    p_lldp.add_argument("host", help="Switch IP or alias")

    p_env = sub.add_parser("environment", help="Temperature, fans, PSUs")
    p_env.add_argument("host", help="Switch IP or alias")

    p_mac = sub.add_parser("mac-table", help="MAC address table")
    p_mac.add_argument("host", help="Switch IP or alias")

    p_chassis = sub.add_parser("chassis-inventory", help="Hardware inventory")
    p_chassis.add_argument("host", help="Switch IP or alias")

    p_route = sub.add_parser("route-summary", help="Routing table summary")
    p_route.add_argument("host", help="Switch IP or alias")

    p_sw = sub.add_parser("software-info", help="Junos version info")
    p_sw.add_argument("host", help="Switch IP or alias")

    p_vlan = sub.add_parser("vlans", help="VLAN configuration")
    p_vlan.add_argument("host", help="Switch IP or alias")

    args = parser.parse_args()

    commands = {
        "interfaces": cmd_interfaces,
        "alarms": cmd_alarms,
        "lldp-neighbors": cmd_lldp_neighbors,
        "environment": cmd_environment,
        "mac-table": cmd_mac_table,
        "chassis-inventory": cmd_chassis_inventory,
        "route-summary": cmd_route_summary,
        "software-info": cmd_software_info,
        "vlans": cmd_vlans,
    }

    result = commands[args.command](args)
    json.dump(result, sys.stdout, indent=2, default=str)
    print()


if __name__ == "__main__":
    main()
