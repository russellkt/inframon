#!/usr/bin/env python3
"""Juniper REST API client for OpenFang shell_exec.

Queries Juniper EX switches via their built-in REST API (rpc-on-http).
No third-party dependencies — uses only Python stdlib.
Reads credentials from /proc/1/environ (container env) since OpenFang's
shell_exec sandbox strips environment variables from subprocesses.

These Junos versions (20.x, 22.x) only support XML responses via the REST
API. This script parses the multipart XML response and converts it to JSON
for easier consumption by the LLM agent.

Usage:
    python3 juniper-api.py <host> <rpc> [param=value ...]

Examples:
    python3 juniper-api.py 10.10.1.10 get-interface-information
    python3 juniper-api.py 10.10.1.10 get-interface-information terse=
    python3 juniper-api.py 10.10.1.9 get-interface-information interface-name=ge-0/0/0
    python3 juniper-api.py 10.10.1.10 get-ethernet-switching-table-information
    python3 juniper-api.py 10.10.1.10 get-lldp-neighbors-information
    python3 juniper-api.py 10.10.1.10 get-alarm-information
    python3 juniper-api.py 10.10.1.10 get-chassis-inventory
    python3 juniper-api.py 10.10.1.10 get-environment-information
    python3 juniper-api.py 10.10.1.10 get-route-summary-information
    python3 juniper-api.py 10.10.1.10 get-software-information
"""

import base64
import json
import os
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET


# Known switches — agent can use hostname aliases
SWITCH_ALIASES = {
    "ex3400": "10.10.1.10",
    "bmic-ex3400-1": "10.10.1.10",
    "ex2300": "10.10.1.9",
    "bmic-ex2300-1": "10.10.1.9",
}


def load_container_env(key):
    """Read env var from container's PID 1 environ (bypasses sandbox stripping)."""
    val = os.environ.get(key)
    if val:
        return val
    try:
        with open("/proc/1/environ", "rb") as f:
            for entry in f.read().split(b"\x00"):
                if entry.startswith(key.encode() + b"="):
                    return entry.decode().split("=", 1)[1]
    except (OSError, PermissionError):
        pass
    return None


def xml_to_dict(element):
    """Recursively convert an XML element to a dict.

    Strips Junos XML namespaces for cleaner output. Handles repeated child
    elements by collecting them into lists.
    """
    # Strip namespace from tag
    tag = element.tag
    if "}" in tag:
        tag = tag.split("}", 1)[1]

    result = {}

    # Add attributes if present
    if element.attrib:
        for k, v in element.attrib.items():
            # Strip namespace from attribute keys too
            if "}" in k:
                k = k.split("}", 1)[1]
            result["@" + k] = v

    children = list(element)
    if children:
        child_dict = {}
        for child in children:
            child_tag, child_val = list(xml_to_dict(child).items())[0]
            if child_tag in child_dict:
                # Convert to list if multiple children with same tag
                if not isinstance(child_dict[child_tag], list):
                    child_dict[child_tag] = [child_dict[child_tag]]
                child_dict[child_tag].append(child_val)
            else:
                child_dict[child_tag] = child_val
        result.update(child_dict)
    elif element.text and element.text.strip():
        # Leaf node with text — return text directly if no attributes
        if not element.attrib:
            return {tag: element.text.strip()}
        result["#text"] = element.text.strip()

    # If result is empty (empty element, no attrs, no children, no text)
    if not result:
        return {tag: None}

    return {tag: result}


def extract_xml_from_multipart(raw_bytes):
    """Extract XML content from Junos multipart response.

    Junos REST API returns multipart/mixed responses with a boundary.
    The XML content is in the body parts between boundaries.
    """
    # Try to find multipart boundary in the raw response
    text = raw_bytes.decode("utf-8", errors="replace")

    # Look for XML content — it may be wrapped in multipart boundaries
    # or returned directly as XML
    xml_start = text.find("<?xml")
    if xml_start == -1:
        # Try finding the root element directly
        xml_start = text.find("<")
    if xml_start == -1:
        return text

    # Find the end of the XML — look for multipart boundary after XML
    xml_content = text[xml_start:]

    # If there's a multipart boundary marker, trim at it
    boundary_pos = xml_content.find("\n--")
    if boundary_pos > 0:
        xml_content = xml_content[:boundary_pos]

    return xml_content.strip()


def api_rpc(host, rpc, params=None, user=None, password=None):
    """Execute a Junos RPC via the REST API.

    Always POSTs to /rpc with the RPC as an XML body element.
    This is the most reliable method — /rpc/<name> doesn't support params.
    """
    url = f"http://{host}:3000/rpc"

    # Build XML body: <rpc-name><param>value</param>...</rpc-name>
    body_parts = []
    if params:
        for k, v in params.items():
            if v:
                body_parts.append(f"<{k}>{v}</{k}>")
            else:
                # Empty value = flag parameter (e.g., terse=)
                body_parts.append(f"<{k}/>")
    body = f"<{rpc}>{''.join(body_parts)}</{rpc}>"

    # HTTP Basic Auth
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
        print(f"HTTP {e.code}: {err_body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Connection error to {host}: {e.reason}", file=sys.stderr)
        sys.exit(1)

    # Extract XML from potential multipart response
    xml_str = extract_xml_from_multipart(raw)

    try:
        root = ET.fromstring(xml_str)
        return xml_to_dict(root)
    except ET.ParseError:
        # If XML parsing fails, return raw text
        return {"raw": xml_str}


def main():
    if len(sys.argv) < 3:
        print("Usage: juniper-api.py <host> <rpc> [param=value ...]", file=sys.stderr)
        print("  host: IP or alias (ex3400, ex2300)", file=sys.stderr)
        print("  rpc:  Junos RPC name (e.g. get-interface-information)", file=sys.stderr)
        print("  params: key=value pairs (e.g. interface-name=ge-0/0/0)", file=sys.stderr)
        print("         Use empty value for flags: terse=", file=sys.stderr)
        print("\nCommon RPCs:", file=sys.stderr)
        print("  get-interface-information       - Interface status and stats", file=sys.stderr)
        print("  get-interface-information terse= - Compact interface list", file=sys.stderr)
        print("  get-ethernet-switching-table-information - MAC table", file=sys.stderr)
        print("  get-lldp-neighbors-information  - LLDP neighbor discovery", file=sys.stderr)
        print("  get-alarm-information           - Active alarms", file=sys.stderr)
        print("  get-chassis-inventory           - Hardware inventory", file=sys.stderr)
        print("  get-environment-information     - Temps, fans, PSUs", file=sys.stderr)
        print("  get-route-summary-information   - Routing table summary", file=sys.stderr)
        print("  get-software-information        - Junos version", file=sys.stderr)
        sys.exit(1)

    host = sys.argv[1]
    rpc = sys.argv[2]

    # Resolve aliases
    host = SWITCH_ALIASES.get(host, host)

    # Parse key=value params
    params = {}
    for arg in sys.argv[3:]:
        if "=" in arg:
            k, v = arg.split("=", 1)
            params[k] = v

    # Load credentials
    user = load_container_env("JUNIPER_USER")
    password = load_container_env("JUNIPER_PASSWORD")

    if not user or not password:
        print("ERROR: JUNIPER_USER and JUNIPER_PASSWORD must be set", file=sys.stderr)
        sys.exit(1)

    result = api_rpc(host, rpc, params or None, user, password)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
