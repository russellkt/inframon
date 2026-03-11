import { type Tool } from "@mariozechner/pi-agent-core";

/**
 * Zabbix API tool - sends JSON-RPC calls to the local proxy server
 */
export const zabbixTool: Tool = {
  name: "zabbix",
  description:
    "Query Zabbix API for problems, events, hosts, and historical data. Use for infrastructure monitoring and alerts.",
  inputSchema: {
    type: "object",
    properties: {
      method: {
        type: "string",
        description:
          "Zabbix API method (e.g., problem.get, event.get, host.get, history.get)",
      },
      params: {
        type: "object",
        description: "API parameters (e.g., filter, output, limit, sortfield)",
        additionalProperties: true,
      },
    },
    required: ["method", "params"],
  },
  execute: async (input: any) => {
    try {
      const response = await fetch("http://localhost:3001/api/zabbix", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          jsonrpc: "2.0",
          method: input.method,
          params: input.params,
          id: Math.floor(Math.random() * 10000),
        }),
      });

      const data = await response.json();

      if (data.error) {
        return `Error: ${data.error.data}`;
      }

      return JSON.stringify(data.result, null, 2);
    } catch (error) {
      return `Failed to call Zabbix API: ${error instanceof Error ? error.message : String(error)}`;
    }
  },
};

/**
 * Proxmox API tool - retrieves Proxmox cluster nodes via SSH proxy
 */
export const proxmoxTool: Tool = {
  name: "proxmox",
  description:
    "Get Proxmox cluster nodes and their status (CPU, memory, disk). Use for infrastructure health checks.",
  inputSchema: {
    type: "object",
    properties: {
      action: {
        type: "string",
        enum: ["get_nodes"],
        description: "Action to perform on Proxmox cluster",
      },
    },
    required: ["action"],
  },
  execute: async (input: any) => {
    try {
      if (input.action === "get_nodes") {
        const response = await fetch("http://localhost:3001/api/proxmox/nodes", {
          method: "GET",
          headers: {
            "Content-Type": "application/json",
          },
        });

        if (!response.ok) {
          return `HTTP ${response.status}: ${await response.text()}`;
        }

        const data = await response.json();
        return JSON.stringify(data, null, 2);
      }

      return "Unknown action";
    } catch (error) {
      return `Failed to call Proxmox API: ${error instanceof Error ? error.message : String(error)}`;
    }
  },
};
