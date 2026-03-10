# 🤖 Enterprise Intelligence Agent

> Enterprise-grade AI investigation agent built with **GitHub Copilot SDK**, **Azure AI Foundry**, **Foundry IQ**, **Work IQ MCP**, and a **Next.js Chat UI**.

[📐 Architecture Details](docs/architecture.md)

---

## 🎯 Overview

This project demonstrates a complete **Enterprise Intelligence Agent** — an enterprise investigation agent that combines Foundry IQ, Work IQ, and Fabric IQ to analyze issues using organizational knowledge, collaboration context, and operational data.

1. Accepts technical questions via a streaming Chat UI
2. Searches **Microsoft Docs** (official documentation) for answers
3. Retrieves **enterprise knowledge** (internal runbooks, architecture docs, SOPs) via **Foundry IQ** (Azure AI Search MCP)
4. Performs deep research via **Azure AI Foundry** (web search-grounded multi-step research)
5. Accesses **M365 data** (Teams, email, calendar) via **Work IQ MCP** when relevant
6. Generates **PowerPoint reports** summarizing findings
7. Uses **GitHub Copilot SDK** as the primary agent orchestrator

---

## 🏗️ Architecture

```
User
 ↓
Next.js Chat UI (port 3000)
 ↓ WebSocket
FastAPI Backend (port 8000)
 ↓
Enterprise Intelligence Agent (GitHub Copilot SDK)
 ├─ Tool: query_ms_docs_tool         → MS Docs MCP Server (npx @microsoft/learn-docs-mcp)
 ├─ Tool: foundry_knowledge_tool     → Azure AI Search MCP (@azure/mcp, azureaisearch namespace)  ← NEW
 ├─ Tool: foundry_deep_research_tool → Azure AI Foundry Agent (WebSearchTool)
 ├─ Tool: generate_powerpoint_tool   → python-pptx (local .pptx generation)
 └─ MCP Server: workiq (session-level, optional) → Work IQ MCP Server (npx @microsoft/workiq mcp)
```

### Knowledge Layers

The agent combines four knowledge layers for comprehensive investigations:

| Layer | Source | Tool | Purpose |
|-------|--------|------|---------|
| Official Docs | Microsoft Learn / MS Docs MCP | `query_ms_docs_tool` | Official product guidance |
| Enterprise Knowledge | Foundry IQ (Azure AI Search) | `foundry_knowledge_tool` | Internal runbooks, architecture docs, SOPs |
| Org Context | Work IQ (Microsoft Graph) | Work IQ MCP (session-level) | Teams / email / collaboration signals |
| Web Research | Azure AI Foundry (web search) | `foundry_deep_research_tool` | Latest public information |

### Component Details

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Chat UI | Next.js + React + Tailwind CSS | Streaming chat with tool execution visibility |
| Backend API | FastAPI + WebSocket | Bridges UI and Copilot SDK; serves report downloads |
| Agent Runtime | GitHub Copilot SDK (Python) | Orchestrates tools, maintains conversation context |
| MS Docs MCP | `@microsoft/learn-docs-mcp` | Queries official Microsoft documentation |
| Foundry IQ | `@azure/mcp` (azureaisearch) | Queries enterprise knowledge bases (Foundry IQ) |
| Deep Research | Azure AI Foundry (`azure-ai-projects`) | Multi-step web research with WebSearch grounding |
| M365 Access | Work IQ MCP (`@microsoft/workiq`) | Session-level MCP integration for emails, meetings, Teams, documents |
| PowerPoint | `python-pptx` | Generates structured .pptx reports |

---

## 🚀 Quick Start

### Prerequisites

| Requirement | Details |
|-------------|---------|
| GitHub Copilot subscription | [Pricing](https://github.com/features/copilot#pricing) · free tier available |
| Copilot CLI | `gh extension install github/gh-copilot` |
| Node.js 18+ | For frontend and MCP servers |
| Python 3.11+ | For backend |
| Azure subscription (optional) | For Foundry Deep Research and Foundry IQ |
| M365 Copilot license (optional) | For Work IQ MCP |

### 1. Clone & Configure

```bash
git clone https://github.com/ishidahra01/copilot-work-iq.git
cd copilot-work-iq

# Copy environment template
cp .env.example .env
# Edit .env with your credentials (see Required Credentials below)
```

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start the backend
python main.py
# Or with uvicorn directly:
# uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The backend API will be available at `http://localhost:8000`.

### 3. Frontend Setup

```bash
cd frontend

# Copy frontend environment file
cp .env.local.example .env.local

# Install dependencies
npm install

# Start development server
npm run dev
```

The chat UI will be available at `http://localhost:3000`.

### 4. Authenticate GitHub Copilot CLI

```bash
# Install and authenticate the Copilot CLI
gh extension install github/gh-copilot
gh auth login
gh copilot --version   # verify it works
```

---

## 🔐 Required Credentials

### Minimum (GitHub Copilot only)

```env
# .env
COPILOT_GITHUB_TOKEN=ghp_your_github_token
```

Or simply ensure you are logged in via `gh auth login` — the SDK picks up your credentials automatically.

### Optional: BYOK (Bring Your Own Key)

If you don't have a GitHub Copilot subscription, you can use your own Azure OpenAI or OpenAI API key:

```env
BYOK_PROVIDER=azure          # openai | azure | anthropic
BYOK_API_KEY=your_key
BYOK_BASE_URL=https://your-resource.openai.azure.com
BYOK_MODEL=gpt-4o
BYOK_AZURE_API_VERSION=2024-10-21
```

### Optional: Azure AI Foundry (Deep Research)

```env
AZURE_FOUNDRY_PROJECT_ENDPOINT=https://your-project.api.azureml.ms
FOUNDRY_MODEL_DEPLOYMENT_NAME=your-deployment-name
```

Set up in [Azure AI Foundry](https://ai.azure.com):
1. Create an Azure AI Foundry project
2. Deploy a model with **Web Search** enabled

### Optional: Foundry IQ (Enterprise Knowledge Retrieval)

```env
AZURE_FOUNDRY_PROJECT_ENDPOINT=https://your-search-resource.search.windows.net
AZURE_SEARCH_INDEX_NAME=foundry-iq
FOUNDRY_IQ_SAMPLE_MODE=false
```

> **Note:** `AZURE_FOUNDRY_PROJECT_ENDPOINT` is reused for Foundry IQ but should point to your **Azure AI Search** endpoint (e.g. `https://your-search-resource.search.windows.net`), not an Azure AI Foundry project endpoint.

Foundry IQ uses **Azure AI Search MCP** (`@azure/mcp`) to query enterprise knowledge bases (internal runbooks, architecture docs, SOPs).

- Reference: [Azure AI Search MCP docs](https://learn.microsoft.com/en-us/azure/search/search-get-started-mcp)
- Set `FOUNDRY_IQ_SAMPLE_MODE=true` to use local sample data (no Azure subscription required)

For local development / demo, use the built-in sample data:
```env
FOUNDRY_IQ_SAMPLE_MODE=true
```

### Optional: Work IQ (M365 Access)

```env
WORKIQ_ENABLED=true
```

Setup:
```bash
npm install -g @microsoft/workiq
workiq login    # authenticate with your Microsoft 365 account
```

Your **M365 tenant admin** must also grant consent at:
`https://login.microsoftonline.com/common/adminconsent?client_id=<workiq-app-id>`

See [Work IQ Admin Instructions](https://github.com/microsoft/work-iq-mcp/blob/main/ADMIN-INSTRUCTIONS.md) for details.

### Optional: MS Docs MCP

```bash
npm install -g @microsoft/learn-docs-mcp
```

If not installed, the agent falls back to providing a direct search URL.

---

## 💬 Demo Walkthrough

### Sample Scenario

> **User:** "We are experiencing authentication issues with Entra ID after conditional access policy changes. What could be wrong?"

**Agent flow:**

1. 📖 **MS Docs search** — queries Microsoft Learn for Entra ID conditional access policies
2. 🏢 **Foundry IQ** — checks internal runbooks and architecture documentation for known issues or procedures
3. 🔬 **Foundry Deep Research** — performs a deep investigation (if Foundry is configured)
4. 💼 **Work IQ** — checks recent admin changes in the tenant (if enabled and relevant)
5. 💬 **Response** — provides root cause analysis, technical details, and remediation steps
6. 📊 **PowerPoint** — generates a downloadable .pptx report on request

### Demo Scenarios for Foundry IQ

| Scenario | Sample Query |
|----------|-------------|
| Internal knowledge troubleshooting | "We enabled a new Microsoft Foundry knowledge source but the agent is not retrieving internal documentation. What should we check?" |
| Pre-rollout validation | "Before rolling out Microsoft Foundry to the EU support team, what validation steps should we follow?" |
| Incident response | "Some users can access Microsoft Foundry chat but cannot retrieve internal knowledge. What internal procedures apply?" |
| Architecture review | "How is our Microsoft Foundry environment connected to enterprise knowledge sources?" |

### UI Features

| Feature | Description |
|---------|-------------|
| 💬 Streaming responses | Messages appear character-by-character as the model generates them |
| 🔧 Tool execution cards | Expandable cards show what tools ran, with arguments and results |
| 📥 Download button | Appears automatically when a PowerPoint is generated |
| 🤖 Model selector | Switch between GPT-4o, GPT-4.1, Claude Sonnet, o4-mini |
| ➕ New chat | Start a fresh conversation while preserving the current context |

---

## 📁 Project Structure

```
.
├── backend/
│   ├── main.py                     # FastAPI app with WebSocket + REST endpoints
│   ├── agent.py                    # Copilot SDK agent orchestrator
│   ├── requirements.txt
│   ├── tools/
│   │   ├── foundry_iq_tool.py      # Foundry IQ enterprise knowledge retrieval (Azure AI Search MCP)
│   │   ├── foundry_tool.py         # Azure AI Foundry deep research (WebSearch)
│   │   ├── pptx_tool.py            # PowerPoint generator (python-pptx)
│   │   ├── msdocs_tool.py          # MS Docs MCP wrapper
│   │   └── __init__.py
│   ├── skills/
│   │   └── support_investigation.py # Agent system prompt / skill definition
│   ├── sample_data/
│   │   └── foundry_iq/             # Sample enterprise knowledge files (for local demo)
│   │       ├── microsoft-foundry-architecture.md
│   │       ├── microsoft-foundry-rollout-checklist.md
│   │       ├── microsoft-foundry-incident-runbook.md
│   │       ├── microsoft-foundry-known-issues.md
│   │       └── microsoft-foundry-postmortem.md
│   └── generated_reports/          # Generated .pptx files (git-ignored)
├── frontend/
│   ├── app/
│   │   ├── page.tsx                # Main page
│   │   ├── layout.tsx              # App layout
│   │   ├── components/
│   │   │   ├── ChatInterface.tsx   # Main chat component (WebSocket, state)
│   │   │   ├── MessageList.tsx     # Message list + typing indicator
│   │   │   ├── ToolExecutionCard.tsx # Collapsible tool execution display
│   │   │   ├── AgentEventCard.tsx  # Collapsible agent event display
│   │   │   └── ModelSelector.tsx   # Model dropdown
│   │   └── lib/
│   │       ├── api.ts              # API/WebSocket client
│   │       └── types.ts            # TypeScript types
│   └── package.json
├── docs/
│   └── architecture.md             # Detailed architecture documentation
├── .env.example                    # Environment variable template
└── README.md
```

---

## 🔌 API Reference

### REST Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/models` | List available Copilot models |
| `POST` | `/sessions` | Create a new chat session |
| `DELETE` | `/sessions/{id}` | Delete a session |
| `GET` | `/reports/{filename}` | Download a generated PowerPoint |

### WebSocket: `ws://localhost:8000/ws/chat/{session_id}`

**Client → Server:**
```json
{ "prompt": "Your question here", "model": "gpt-4o" }
```

**Server → Client (streaming events):**
```json
{ "type": "assistant.message_delta", "content": "..." }
{ "type": "tool.execution_start", "tool_name": "query_ms_docs_tool", "args": {...} }
{ "type": "tool.execution_complete", "tool_name": "query_ms_docs_tool", "result": "..." }
{ "type": "assistant.message", "content": "..." }
{ "type": "session.idle" }
{ "type": "error", "message": "..." }
```

---

## 🧩 Extending the Agent

### Adding a New Tool

1. Create a new file in `backend/tools/`:

```python
from pydantic import BaseModel, Field
from copilot import define_tool

class MyToolParams(BaseModel):
    query: str = Field(description="The input to my tool")

@define_tool(description="Description of what this tool does")
async def my_custom_tool(params: MyToolParams) -> str:
    # Your implementation here
    return "Tool result"
```

2. Import and add it to `tools/__init__.py`
3. Add it to the `tools` list in `agent.py`

### Modifying the Agent Persona

Edit `backend/skills/support_investigation.py` to change:
- The agent's role and expertise
- The investigation workflow
- Response formatting
- Tool usage guidelines

---

## 💡 Stretch Goals

- [ ] Token usage / cost tracking dashboard
- [ ] Multi-model comparison mode (run the same query on multiple models)
- [ ] Safety guardrails and content filtering
- [ ] Observability dashboard (traces, latency, tool usage stats)
- [ ] Conversation export (PDF, Markdown)
- [ ] Session persistence across page reloads

---

## 📖 References

- [GitHub Copilot SDK](https://github.com/github/copilot-sdk)
- [GitHub Copilot SDK Cookbook](https://github.com/github/awesome-copilot/tree/main/cookbook/copilot-sdk)
- [Azure AI Foundry Deep Research](https://azure.microsoft.com/en-us/blog/introducing-deep-research-in-azure-ai-foundry-agent-service/)
- [Azure AI Search MCP (Foundry IQ)](https://learn.microsoft.com/en-us/azure/search/search-get-started-mcp)
- [Work IQ MCP](https://github.com/microsoft/work-iq-mcp)
- [Microsoft Learn Docs MCP](https://github.com/MicrosoftDocs/mcp)
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io)

---

## 📄 License

MIT — see [LICENSE](LICENSE)
