"""
Foundry IQ Tool — Enterprise Knowledge Retrieval.

Queries enterprise knowledge bases using Foundry IQ (powered by Azure AI Search).

Supports two modes:
  - Sample data mode (FOUNDRY_IQ_SAMPLE_MODE=true):
      Returns results from local demo markdown files under
      backend/sample_data/foundry_iq/.  Useful for local development
      and demos without a live Azure subscription.
  - Real mode (default):
      Calls the Azure AI Search MCP server to query a Foundry IQ index.
      Requires AZURE_FOUNDRY_PROJECT_ENDPOINT (Azure AI Search endpoint)
      and AZURE_SEARCH_INDEX_NAME to be configured.

Reference:
  https://learn.microsoft.com/en-us/azure/search/search-get-started-mcp
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import pathlib

from pydantic import BaseModel, Field
from copilot import define_tool

logger = logging.getLogger(__name__)

# Azure AI Search MCP server (part of the @azure/mcp package).
# See: https://learn.microsoft.com/en-us/azure/search/search-get-started-mcp
_MCP_SERVER_CMD = [
    "npx",
    "-y",
    "@azure/mcp@latest",
    "server",
    "start",
    "--namespace",
    "azureaisearch",
]

_SAMPLE_DATA_DIR = (
    pathlib.Path(__file__).parent.parent / "sample_data" / "foundry_iq"
)

# Maximum number of top documents to include in a response.
_TOP_K = 3


class FoundryKnowledgeParams(BaseModel):
    query: str = Field(description="Enterprise knowledge search query")


@define_tool(
    description=(
        "Search enterprise runbooks, architecture documentation, incident postmortems, "
        "rollout checklists, and operational procedures using Foundry IQ. "
        "Use this tool when the question involves internal procedures, organization-specific "
        "configurations, known issues documented internally, or architectural guidance that "
        "would not be found in public Microsoft documentation."
    )
)
async def foundry_knowledge_tool(params: FoundryKnowledgeParams) -> str:
    """Search enterprise knowledge using Foundry IQ."""
    sample_mode = (
        os.environ.get("FOUNDRY_IQ_SAMPLE_MODE", "false").lower() == "true"
    )

    if sample_mode:
        return await _search_sample_data(params.query)

    result = await _query_via_mcp(params.query)
    if result:
        return result

    return _not_configured_message(params.query)


# ---------------------------------------------------------------------------
# Sample data mode
# ---------------------------------------------------------------------------

async def _search_sample_data(query: str) -> str:
    """Search through sample markdown files for relevant content."""
    if not _SAMPLE_DATA_DIR.exists():
        return (
            f"[Foundry IQ - Sample Mode] Sample data directory not found: "
            f"{_SAMPLE_DATA_DIR}"
        )

    query_lower = query.lower()
    query_terms = [t for t in query_lower.split() if len(t) > 2]

    matches: list[tuple[int, str, str]] = []
    for md_file in sorted(_SAMPLE_DATA_DIR.glob("*.md")):
        content = md_file.read_text(encoding="utf-8")
        content_lower = content.lower()
        score = sum(1 for term in query_terms if term in content_lower)
        if score > 0:
            matches.append((score, md_file.name, content))

    if not matches:
        available = [f.name for f in sorted(_SAMPLE_DATA_DIR.glob("*.md"))]
        return (
            f"[Foundry IQ - Sample Mode] No relevant enterprise knowledge found "
            f"for: '{query}'\n"
            f"Available knowledge base documents: {available}"
        )

    matches.sort(key=lambda x: -x[0])

    results: list[str] = []
    for _score, filename, content in matches[:_TOP_K]:
        lines = content.splitlines()
        snippet = "\n".join(lines[:60])
        if len(lines) > 60:
            snippet += f"\n\n[...content truncated. Document: {filename}]"
        results.append(f"### 📄 {filename}\n\n{snippet}")

    header = (
        f"[Foundry IQ - Sample Mode] Found {len(matches)} relevant "
        f"document(s) for: '{query}'\n\n"
    )
    return header + "\n\n---\n\n".join(results)


# ---------------------------------------------------------------------------
# Real mode — Azure AI Search MCP
# ---------------------------------------------------------------------------

async def _query_via_mcp(query: str) -> str | None:
    """
    Call the Azure AI Search MCP server to retrieve enterprise knowledge.

    The MCP server is started as a short-lived subprocess (same pattern as
    msdocs_tool.py).  The Azure AI Search endpoint is read from
    AZURE_FOUNDRY_PROJECT_ENDPOINT and the index name from
    AZURE_SEARCH_INDEX_NAME (defaults to "foundry-iq").

    Reference:
      https://learn.microsoft.com/en-us/azure/search/search-get-started-mcp
    """
    endpoint = os.environ.get("AZURE_FOUNDRY_PROJECT_ENDPOINT")
    index_name = os.environ.get("AZURE_SEARCH_INDEX_NAME", "foundry-iq")

    if not endpoint:
        return None

    init_req = json.dumps({
        "jsonrpc": "2.0",
        "id": 0,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "support-agent", "version": "1.0"},
        },
    })

    tool_req = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "azureaisearch_query_index",
            "arguments": {
                "indexName": index_name,
                "query": query,
                "queryType": "semantic",
                "top": _TOP_K,
            },
        },
    })

    env = {**os.environ, "AZURE_SEARCH_ENDPOINT": endpoint}

    try:
        proc = await asyncio.create_subprocess_exec(
            *_MCP_SERVER_CMD,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        stdout, _ = await asyncio.wait_for(
            proc.communicate(
                input=(init_req + "\n" + tool_req + "\n").encode()
            ),
            timeout=30,
        )

        for line in stdout.decode().splitlines():
            if not line.strip():
                continue
            try:
                response = json.loads(line)
                if response.get("id") == 1:
                    result = response.get("result", {})
                    content = result.get("content", [])
                    texts = [
                        c.get("text", "")
                        for c in content
                        if c.get("type") == "text"
                    ]
                    if texts:
                        return (
                            f"[Foundry IQ] Search results for: '{query}'\n\n"
                            + "\n\n".join(texts)
                        )
            except json.JSONDecodeError:
                continue

    except (asyncio.TimeoutError, FileNotFoundError, Exception) as exc:
        logger.debug("Foundry IQ MCP server unavailable: %s", exc)

    return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _not_configured_message(query: str) -> str:
    return (
        "[Foundry IQ] Foundry IQ is not configured. "
        "Set AZURE_FOUNDRY_PROJECT_ENDPOINT to your Azure AI Search endpoint "
        "and AZURE_SEARCH_INDEX_NAME to your Foundry IQ index name to enable "
        "real enterprise knowledge retrieval.\n"
        "Set FOUNDRY_IQ_SAMPLE_MODE=true to use sample data for local testing.\n"
        f"Query: {query}"
    )
