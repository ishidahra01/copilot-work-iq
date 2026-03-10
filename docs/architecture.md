# Architecture Deep Dive

## Component Interaction Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                       User Browser                           │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                   Next.js Chat UI                       │ │
│  │                                                         │ │
│  │  ┌──────────────┐  ┌─────────────┐  ┌──────────────┐  │ │
│  │  │ ChatInterface│  │ MessageList │  │ ModelSelector│  │ │
│  │  │  (WebSocket) │  │  + Markdown │  │              │  │ │
│  │  └──────┬───────┘  └─────────────┘  └──────────────┘  │ │
│  │         │ ToolExecutionCard / AgentEventCard (expandable)│ │
│  └─────────┼───────────────────────────────────────────────┘ │
└────────────┼────────────────────────────────────────────────┘
             │ WebSocket (ws://localhost:8000/ws/chat/{id})
             │ Streaming JSON events
             ▼
┌─────────────────────────────────────────────────────────────┐
│               FastAPI Backend (Python)                        │
│                                                              │
│  /ws/chat/{id}  /models  /sessions  /reports/{file}          │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │         Enterprise Intelligence Agent (agent.py)        │ │
│  │                                                         │ │
│  │  ┌─────────────────────────────────────────────────┐   │ │
│  │  │           GitHub Copilot SDK (Python)            │   │ │
│  │  │                                                   │   │ │
│  │  │  CopilotClient → CopilotSession                  │   │ │
│  │  │  - Manages CLI subprocess lifecycle              │   │ │
│  │  │  - JSON-RPC over stdio                           │   │ │
│  │  │  - Streaming events (message_delta, tool.*)      │   │ │
│  │  │  - Custom tools + system message                 │   │ │
│  │  └─────────────────────────────────────────────────┘   │ │
│  │                                                         │ │
│  │  Custom Tools:                                          │ │
│  │  ┌───────────────┐  ┌─────────────────────────────┐   │ │
│  │  │query_ms_docs  │  │foundry_knowledge             │   │ │
│  │  │(msdocs_tool)  │  │(foundry_iq_tool)  ← NEW     │   │ │
│  │  └───────┬───────┘  └──────────────┬──────────────┘   │ │
│  │          │                          │ Azure AI Search   │ │
│  │  ┌───────────────────────────────────────────────┐     │ │
│  │  │foundry_deep_research (foundry_tool)           │     │ │
│  │  └───────────────────────────────────────────────┘     │ │
│  │  ┌───────────────────────────────────────────────┐     │ │
│  │  │generate_powerpoint (pptx_tool)                │     │ │
│  │  └───────────────────────────────────────────────┘     │ │
│  │                                                         │ │
│  │  Session-level MCP Server (optional):                   │ │
│  │  ┌─────────────────────────────────────────────────┐   │ │
│  │  │  workiq MCP (when WORKIQ_ENABLED=true)           │   │ │
│  │  └─────────────────────────────────────────────────┘   │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
              │                │                    │
    ┌─────────▼──────┐  ┌──────▼───────────┐  ┌───▼──────────────────────┐
    │  MS Docs MCP   │  │  Azure AI Search  │  │  Azure AI Foundry         │
    │  (Node stdio)  │  │  MCP (@azure/mcp) │  │  Agent Service (REST)     │
    │                │  │                   │  │                           │
    │ @microsoft/    │  │ azureaisearch     │  │ - WebSearchTool           │
    │  learn-docs-mcp│  │ namespace         │  │ - Multi-step reasoning    │
    └────────────────┘  │ - Foundry IQ index│  └───────────────────────────┘
                        └───────────────────┘
    ┌────────────────┐
    │  Work IQ MCP   │
    │  (Node stdio)  │
    │                │
    │ @microsoft/    │
    │  workiq        │
    │ - Email        │
    │ - Calendar     │
    │ - Teams        │
    └────────────────┘
```

## Knowledge Layers

The Enterprise Intelligence Agent combines four knowledge layers for comprehensive investigations:

| Layer               | Source                          | Tool                          | Purpose                                      |
|---------------------|---------------------------------|-------------------------------|----------------------------------------------|
| Official Docs       | Microsoft Learn / MS Docs MCP   | `query_ms_docs_tool`          | Official product guidance                    |
| Enterprise Knowledge| Foundry IQ (Azure AI Search)    | `foundry_knowledge_tool`      | Internal runbooks, architecture docs, SOPs   |
| Org Context         | Work IQ (Microsoft Graph)       | `query_workiq_tool` (via MCP) | Teams / email / collaboration signals        |
| Web Research        | Azure AI Foundry (web search)   | `foundry_deep_research_tool`  | Latest public information                    |

Investigation reasoning flow:

```
Question
 ↓
Official Docs (query_ms_docs_tool)
 ↓
Enterprise Knowledge (foundry_knowledge_tool via Foundry IQ)
 ↓
Org Context (query_workiq_tool via Work IQ MCP)
 ↓
Web Research (foundry_deep_research_tool)
 ↓
Root cause analysis + Recommended action
```

## Data Flow

### 1. User Sends a Message

```
User types message → ChatInterface.sendMessage()
  → WebSocket.send({ prompt, model })
  → FastAPI /ws/chat/{id}
  → agent.send_message(session_id, prompt, model)
  → copilot_session.send({ prompt })
```

### 2. Agent Processes (Copilot SDK)

```
Copilot CLI receives prompt
  → LLM plans tool calls
  → Emits: tool.execution_start (tool_name, args)
  → Calls tool handler (e.g., query_ms_docs_tool)
  → Emits: tool.execution_complete (result)
  → LLM synthesizes results
  → Emits: assistant.message_delta (streaming)
  → Emits: assistant.message (final)
  → Emits: session.idle
```

### 3. Events Streamed to Frontend

```
FastAPI receives events via session.on(handler)
  → Puts events in asyncio.Queue
  → WebSocket sends JSON events to browser
  → ChatInterface.onmessage() handles each event:
    - message_delta → appends to streaming message
    - tool.execution_start → adds ToolExecutionCard (running state)
    - tool.execution_complete → updates ToolExecutionCard (complete state)
    - session.idle → marks message as complete
```

## Tool Architecture

### query_ms_docs_tool
- Spawns `npx -y @microsoft/learn-docs-mcp` subprocess
- Sends MCP JSON-RPC `tools/call` request over stdio
- Falls back to returning a Microsoft Learn search URL if MCP unavailable

### foundry_knowledge_tool *(NEW)*
- Queries enterprise knowledge bases using **Foundry IQ** (powered by Azure AI Search)
- Calls the **Azure AI Search MCP server** (`@azure/mcp` with `azureaisearch` namespace)
  via a short-lived JSON-RPC subprocess, identical in pattern to `query_ms_docs_tool`
- Supports a **sample data mode** (`FOUNDRY_IQ_SAMPLE_MODE=true`) that searches local
  markdown files in `backend/sample_data/foundry_iq/` — useful for local development
  and demos without a live Azure subscription
- Environment variables:
  - `AZURE_FOUNDRY_PROJECT_ENDPOINT` — Azure AI Search endpoint URL
  - `AZURE_SEARCH_INDEX_NAME` — Foundry IQ index name (default: `foundry-iq`)
  - `FOUNDRY_IQ_SAMPLE_MODE` — set to `true` for local sample data mode
- Reference: https://learn.microsoft.com/en-us/azure/search/search-get-started-mcp

### foundry_deep_research_tool
- Uses `azure-ai-projects` Python SDK
- Creates or reuses a named agent with `WebSearchTool`
- Invokes research via the OpenAI-compatible responses API
- Reads `FOUNDRY_PROJECT_ENDPOINT` (or `AZURE_FOUNDRY_PROJECT_ENDPOINT`) and `FOUNDRY_MODEL_DEPLOYMENT_NAME` (or `AZURE_FOUNDRY_DEEP_RESEARCH_MODEL`) from environment

### generate_powerpoint_tool
- Uses `python-pptx` to create a structured 5-slide deck
- Saves to `backend/generated_reports/report_{uuid}.pptx`
- Returns a download path; FastAPI `/reports/{filename}` serves the file

### Work IQ MCP (session-level)
- Configured as a session-level MCP server when `WORKIQ_ENABLED=true`
- Spawns `npx -y @microsoft/workiq mcp` subprocess
- Exposes M365 tools (email, calendar, Teams, OneDrive, people) directly to the Copilot SDK session
- No custom Python wrapper needed — the Copilot SDK handles MCP communication

## Session Management

- Each chat conversation has a unique `session_id` (UUID)
- The FastAPI backend maintains a `{session_id → CopilotSession}` dict
- Sessions persist until explicitly deleted or the server restarts
- WebSocket is one-to-one with a session
- The Copilot SDK maintains full conversation history per session (infinite sessions enabled by default)

## Authentication

### GitHub Copilot SDK
- Reads `COPILOT_GITHUB_TOKEN` env var, or
- Uses stored CLI credentials from `gh auth login`, or
- Uses BYOK provider config (`BYOK_PROVIDER`, `BYOK_API_KEY`, etc.)

### Azure AI Foundry
- Uses `DefaultAzureCredential` (supports managed identity, CLI login, env vars)
- Requires `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID` for service principal

### Work IQ
- Interactive OAuth via `workiq login`
- Tenant admin must grant consent for M365 data access
