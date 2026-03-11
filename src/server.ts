import express, { Express, Request, Response } from "express";
import cors from "cors";
import dotenv from "dotenv";
import { execSync } from "child_process";

dotenv.config();

const app: Express = express();
const PORT_API = process.env.PORT_API || "3001";
const ZABBIX_API_URL = process.env.ZABBIX_API_URL;
const ZABBIX_API_TOKEN = process.env.ZABBIX_API_TOKEN;

// Middleware
app.use(cors());
app.use(express.json());

// Health check endpoint
app.get("/health", (req: Request, res: Response) => {
  res.json({ status: "ok" });
});

// Proxy Zabbix API calls
app.post("/api/zabbix", async (req: Request, res: Response) => {
  try {
    if (!ZABBIX_API_URL || !ZABBIX_API_TOKEN) {
      return res.status(500).json({
        error: "Zabbix API configuration missing",
        missing: {
          url: !ZABBIX_API_URL,
          token: !ZABBIX_API_TOKEN,
        },
      });
    }

    const response = await fetch(ZABBIX_API_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${ZABBIX_API_TOKEN}`,
      },
      body: JSON.stringify(req.body),
    });

    const data = await response.json();
    res.json(data);
  } catch (error) {
    console.error("Zabbix proxy error:", error);
    res.status(500).json({
      error: error instanceof Error ? error.message : "Unknown error",
    });
  }
});

// Get Proxmox nodes via SSH
app.get("/api/proxmox/nodes", (req: Request, res: Response) => {
  try {
    // SSH into pve-r720 and run pvesh to get cluster nodes
    const command =
      'ssh -o StrictHostKeyChecking=no pve-r720.bmic.local "pvesh get /nodes --output-format json"';

    const output = execSync(command, {
      encoding: "utf-8",
      timeout: 10000,
    });

    const data = JSON.parse(output);
    res.json(data);
  } catch (error) {
    console.error("Proxmox proxy error:", error);
    res.status(500).json({
      error: error instanceof Error ? error.message : "Unknown error",
      hint: "Ensure SSH key authentication is configured for pve-r720.bmic.local",
    });
  }
});

// Start server
app.listen(PORT_API, () => {
  console.log(`Inframon API server listening on port ${PORT_API}`);
  console.log(`Zabbix API: ${ZABBIX_API_URL}`);
  console.log(`Health check: http://localhost:${PORT_API}/health`);
});
