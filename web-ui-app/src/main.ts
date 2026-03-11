import "@mariozechner/mini-lit/dist/ThemeToggle.js";
import { Agent, type AgentMessage } from "@mariozechner/pi-agent-core";
import { getModel } from "@mariozechner/pi-ai";
import {
  ChatPanel,
  ApiKeyPromptDialog,
  AppStorage,
  IndexedDBStorageBackend,
  ProviderKeysStore,
  SessionsStore,
  SettingsStore,
  CustomProvidersStore,
  setAppStorage,
  SessionListDialog,
} from "@mariozechner/pi-web-ui";
import { html, render } from "lit";
import { Plus, Settings, Clock } from "lucide";
import { Button } from "@mariozechner/mini-lit/dist/Button.js";
import "./app.css";
import { icon } from "@mariozechner/mini-lit";
import { zabbixTool, proxmoxTool } from "./tools";

// Create stores
const settings = new SettingsStore();
const providerKeys = new ProviderKeysStore();
const sessions = new SessionsStore();
const customProviders = new CustomProvidersStore();

// Create backend
const backend = new IndexedDBStorageBackend({
  dbName: "inframon-web-ui",
  version: 1,
  stores: [
    settings.getConfig(),
    SessionsStore.getMetadataConfig(),
    providerKeys.getConfig(),
    customProviders.getConfig(),
    sessions.getConfig(),
  ],
});

// Wire backend to stores
settings.setBackend(backend);
providerKeys.setBackend(backend);
customProviders.setBackend(backend);
sessions.setBackend(backend);

// Create and set app storage
const storage = new AppStorage(settings, providerKeys, sessions, customProviders, backend);
setAppStorage(storage);

let currentSessionId: string | undefined;
let currentTitle = "";
let agent: Agent;
let chatPanel: ChatPanel;
let agentUnsubscribe: (() => void) | undefined;

const generateTitle = (messages: AgentMessage[]): string => {
  const firstUserMsg = messages.find((m) => m.role === "user" || m.role === "user-with-attachments");
  if (!firstUserMsg) return "";

  let text = "";
  const content = firstUserMsg.content;

  if (typeof content === "string") {
    text = content;
  } else {
    const textBlocks = (content as any[]).filter((c) => c.type === "text");
    text = textBlocks.map((c) => c.text || "").join(" ");
  }

  text = text.trim();
  if (!text) return "";

  const sentenceEnd = text.search(/[.!?]/);
  if (sentenceEnd > 0 && sentenceEnd <= 50) {
    return text.substring(0, sentenceEnd + 1);
  }
  return text.length <= 50 ? text : `${text.substring(0, 47)}...`;
};

const shouldSaveSession = (messages: AgentMessage[]): boolean => {
  const hasUserMsg = messages.some((m: any) => m.role === "user" || m.role === "user-with-attachments");
  const hasAssistantMsg = messages.some((m: any) => m.role === "assistant");
  return hasUserMsg && hasAssistantMsg;
};

const saveSession = async () => {
  if (!storage.sessions || !currentSessionId || !agent || !currentTitle) return;

  const state = agent.state;
  if (!shouldSaveSession(state.messages)) return;

  try {
    const sessionData = {
      id: currentSessionId,
      title: currentTitle,
      model: state.model!,
      thinkingLevel: state.thinkingLevel,
      messages: state.messages,
      createdAt: new Date().toISOString(),
      lastModified: new Date().toISOString(),
    };

    const metadata = {
      id: currentSessionId,
      title: currentTitle,
      createdAt: sessionData.createdAt,
      lastModified: sessionData.lastModified,
      messageCount: state.messages.length,
      modelId: state.model?.id || null,
      thinkingLevel: state.thinkingLevel,
      preview: generateTitle(state.messages),
    };

    await storage.sessions.save(sessionData, metadata);
  } catch (err) {
    console.error("Failed to save session:", err);
  }
};

const updateUrl = (sessionId: string) => {
  const url = new URL(window.location.href);
  url.searchParams.set("session", sessionId);
  window.history.replaceState({}, "", url);
};

const createAgent = async (initialState?: any) => {
  if (agentUnsubscribe) {
    agentUnsubscribe();
  }

  agent = new Agent({
    initialState: initialState || {
      systemPrompt: `You are inframon, an infrastructure troubleshooting agent for BMIC's Zabbix + Proxmox environment.

## Available Tools
- **zabbix**: Query Zabbix API for problems, events, hosts, and historical data
- **proxmox**: Get Proxmox cluster nodes and their health status

When an operator describes an infrastructure problem:
1. Use the zabbix tool to query for alert details, historical trends, and related events
2. Use the proxmox tool to check host health, resource usage, and cluster status
3. Provide clear findings and recommendations based on the data
4. Be ready to execute approved remediation steps

Be concise and actionable. Explain what data you're checking and why.

**Note:** Configure your AI provider in Settings (⚙️) before starting.`,
      model: undefined,
      thinkingLevel: "off",
      messages: [],
      tools: [],
    },
  });

  agentUnsubscribe = agent.subscribe((event: any) => {
    if (event.type === "state-update") {
      const messages = event.state.messages;

      if (!currentTitle && shouldSaveSession(messages)) {
        currentTitle = generateTitle(messages);
      }

      if (!currentSessionId && shouldSaveSession(messages)) {
        currentSessionId = crypto.randomUUID();
        updateUrl(currentSessionId);
      }

      if (currentSessionId) {
        saveSession();
      }

      renderApp();
    }
  });

  await chatPanel.setAgent(agent, {
    onApiKeyRequired: async (provider: string) => {
      return await ApiKeyPromptDialog.prompt(provider);
    },
    toolsFactory: (_agent) => [zabbixTool, proxmoxTool],
  });
};

const newSession = () => {
  const url = new URL(window.location.href);
  url.search = "";
  window.location.href = url.toString();
};

const openSessionHistory = async () => {
  try {
    const selected = await SessionListDialog.show(sessions);
    if (selected) {
      const url = new URL(window.location.href);
      url.searchParams.set("session", selected);
      window.location.href = url.toString();
    }
  } catch (err) {
    console.error("Failed to open session history:", err);
  }
};

const renderApp = () => {
  const app = document.getElementById("app");
  if (!app) return;

  // Get URL params for alert context
  const urlParams = new URLSearchParams(window.location.search);
  const alertId = urlParams.get("alert_id");
  const host = urlParams.get("host");
  const problem = urlParams.get("problem");

  // Build alert banner HTML
  const alertBanner = alertId
    ? html`<div class="bg-yellow-900 bg-opacity-20 border-b border-yellow-700 px-4 py-2 text-sm text-yellow-200">
        <span class="font-semibold">Alert:</span> ${host} — ${problem}
        <span class="text-xs text-yellow-300 ml-2">(ID: ${alertId})</span>
      </div>`
    : html``;

  const appHtml = html`
    <div class="w-full h-screen flex flex-col bg-background text-foreground overflow-hidden">
      <!-- Alert Banner (if active) -->
      ${alertBanner}

      <!-- Header -->
      <div class="flex items-center justify-between border-b border-border shrink-0 px-4 py-3">
        <div class="text-xl font-semibold">Inframon</div>
        <div class="flex items-center gap-2">
          ${Button({
            variant: "ghost",
            size: "sm",
            children: icon(Clock, "sm"),
            onClick: openSessionHistory,
            title: "Session History",
          })}
          ${Button({
            variant: "ghost",
            size: "sm",
            children: icon(Plus, "sm"),
            onClick: newSession,
            title: "New Session",
          })}
          <theme-toggle></theme-toggle>
          ${Button({
            variant: "ghost",
            size: "sm",
            children: icon(Settings, "sm"),
            title: "Settings",
          })}
        </div>
      </div>

      <!-- Chat Panel -->
      ${chatPanel}
    </div>
  `;

  render(appHtml, app);
};

async function initApp() {
  const app = document.getElementById("app");
  if (!app) throw new Error("App container not found");

  render(html`<div class="w-full h-screen flex items-center justify-center bg-background text-foreground"><div class="text-muted-foreground">Loading...</div></div>`, app);

  chatPanel = new ChatPanel();

  const urlParams = new URLSearchParams(window.location.search);
  const alertId = urlParams.get("alert_id");
  const host = urlParams.get("host");
  const problem = urlParams.get("problem");

  if (alertId) {
    currentTitle = `${host}: ${problem}`;
    currentSessionId = crypto.randomUUID();
  }

  await createAgent();

  // Pre-populate with alert context if available
  if (alertId && host && problem) {
    agent.steer({
      role: "user",
      content: `Alert: ${host} — ${problem} (ID: ${alertId}). Please investigate and report your initial findings.`,
    });
  }

  renderApp();
}

initApp().catch(console.error);
