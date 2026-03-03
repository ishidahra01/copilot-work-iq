"""
Microsoft Docs MCP Tool.

Queries Microsoft Learn / Docs using the official MS Docs MCP server.
Falls back to direct HTTPS search when the MCP server is unavailable.
"""
from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import sys
from pydantic import BaseModel, Field
from copilot import define_tool

logger = logging.getLogger(__name__)

_MCP_SERVER_CMD = ["npx", "-y", "@microsoft/learn-docs-mcp"]


class QueryMsDocsParams(BaseModel):
    query: str = Field(description="Technical question or topic to search in Microsoft documentation")


@define_tool(
    description=(
        "Search Microsoft documentation (Microsoft Learn / MS Docs) for technical information. "
        "Use this tool first when answering questions about Microsoft products, Azure, "
        "Microsoft 365, Entra ID, Windows, or any other Microsoft technology."
    )
)
async def query_ms_docs_tool(params: QueryMsDocsParams) -> str:
    """Query Microsoft documentation via the MS Docs MCP server or fallback search."""
    result = await _query_via_mcp_server(params.query)
    if result:
        return result
    return await _fallback_search(params.query)


async def _query_via_mcp_server(query: str) -> str | None:
    """Attempt to call the MS Docs MCP server via JSON-RPC over stdio."""
    try:
        request = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "search_documentation",
                "arguments": {"query": query},
            },
        })

        proc = await asyncio.create_subprocess_exec(
            *_MCP_SERVER_CMD,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Send initialization + tool call
        init_req = json.dumps({"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "support-agent", "version": "1.0"},
        }})
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=(init_req + "\n" + request + "\n").encode()),
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
                    texts = [c.get("text", "") for c in content if c.get("type") == "text"]
                    if texts:
                        return "\n\n".join(texts)
            except json.JSONDecodeError:
                continue

    except (asyncio.TimeoutError, FileNotFoundError, Exception) as exc:
        logger.debug("MS Docs MCP server unavailable: %s", exc)

    return None


async def _fallback_search(query: str) -> str:
    """Return a helpful message with documentation search guidance."""
    encoded = query.replace(" ", "+")
    return (
        f"[MS Docs] MCP server not available. "
        f"Please search Microsoft Learn directly:\n"
        f"https://learn.microsoft.com/en-us/search/?terms={encoded}\n\n"
        f"To enable the MCP server, run: npm install -g @microsoft/learn-docs-mcp\n"
        f"Then restart the backend."
    )
