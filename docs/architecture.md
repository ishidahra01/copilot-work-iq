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
│  │         │ ToolExecutionCard (expandable)                │ │
│  └─────────┼───────────────────────────────────────────────┘ │
└────────────┼────────────────────────────────────────────────┘
             │ WebSocket (ws://localhost:8000/ws/chat/{id})
             │ Streaming JSON events
             ▼
┌─────────────────────────────────────────────────────────────┐
│                  FastAPI Backend (Python)                     │
│                                                              │
│  /ws/chat/{id}  /models  /sessions  /reports/{file}          │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              SupportAgent (agent.py)                    │ │
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
│  │  │query_ms_docs  │  │foundry_deep_research         │   │ │
│  │  │(msdocs_tool)  │  │(foundry_tool)                │   │ │
│  │  └───────┬───────┘  └──────────────┬──────────────┘   │ │
│  │          │                          │                   │ │
│  │  ┌───────────────┐  ┌─────────────────────────────┐   │ │
│  │  │query_workiq   │  │generate_powerpoint           │   │ │
│  │  │(workiq_tool)  │  │(pptx_tool)                   │   │ │
│  │  └───────┬───────┘  └──────────────┬──────────────┘   │ │
│  └──────────┼──────────────────────────┼───────────────────┘ │
└─────────────┼──────────────────────────┼─────────────────────┘
              │                          │
    ┌─────────▼─────────┐    ┌───────────▼──────────────┐
    │   MS Docs MCP      │    │  Azure AI Foundry         │
    │   (Node.js stdio)  │    │  Agent Service (REST)     │
    │                    │    │                           │
    │ @microsoft/        │    │ - DeepResearchTool        │
    │  learn-docs-mcp    │    │ - Bing Search grounding   │
    └────────────────────┘    │ - Multi-step reasoning    │
                              └───────────────────────────┘
    ┌────────────────────┐
    │  Work IQ MCP       │
    │  (Node.js stdio)   │
    │                    │
    │ @microsoft/workiq  │
    │ - Email, Calendar  │
    │ - Teams, OneDrive  │
    │ - People / Org     │
    └────────────────────┘
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

### foundry_deep_research_tool
- Uses `azure-ai-projects` Python SDK
- Creates a temporary agent with `DeepResearchTool` (Bing grounding)
- Runs on a new thread, polls for completion
- Deletes the temporary agent after use

### query_workiq_tool
- Spawns `npx -y @microsoft/workiq mcp` subprocess
- Sends MCP JSON-RPC `tools/call` with `ask` tool
- Only active when `WORKIQ_ENABLED=true` in environment

### generate_powerpoint_tool
- Uses `python-pptx` to create a structured 5-slide deck
- Saves to `backend/generated_reports/report_{uuid}.pptx`
- Returns a download path; FastAPI `/reports/{filename}` serves the file

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
