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
} from "@mariozechner/pi-web-ui";
import { html, render } from "lit";
import { Plus, Settings, Clock } from "lucide";
import { Button } from "@mariozechner/mini-lit/dist/Button.js";
import "./app.css";
import { icon } from "@mariozechner/mini-lit";

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

When an operator describes an infrastructure problem:
1. Ask clarifying questions if needed
2. Use your available skills to investigate
3. Provide clear findings and recommendations
4. Be ready to execute approved remediation steps

Be concise and actionable.`,
      model: getModel("anthropic", "claude-opus-4-6"),
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
  });
};

const newSession = () => {
  const url = new URL(window.location.href);
  url.search = "";
  window.location.href = url.toString();
};

const renderApp = () => {
  const app = document.getElementById("app");
  if (!app) return;

  const appHtml = html`
    <div class="w-full h-screen flex flex-col bg-background text-foreground overflow-hidden">
      <!-- Header -->
      <div class="flex items-center justify-between border-b border-border shrink-0 px-4 py-3">
        <div class="text-xl font-semibold">Inframon</div>
        <div class="flex items-center gap-2">
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
      content: `Alert: ${host} - ${problem} (ID: ${alertId})`,
    });
  }

  renderApp();
}

initApp().catch(console.error);
