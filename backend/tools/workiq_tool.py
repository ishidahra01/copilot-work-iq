"""
Microsoft Work IQ MCP Tool.

Queries Microsoft 365 data (emails, meetings, Teams messages, documents,
people / org charts) via the Work IQ MCP server.

Work IQ MCP server: https://github.com/microsoft/work-iq-mcp
Install:  npm install -g @microsoft/workiq
Run MCP:  workiq mcp   (or npx -y @microsoft/workiq mcp)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from pydantic import BaseModel, Field
from copilot import define_tool

logger = logging.getLogger(__name__)

_WORKIQ_ENABLED = os.environ.get("WORKIQ_ENABLED", "false").lower() == "true"
_MCP_SERVER_CMD = ["npx", "-y", "@microsoft/workiq", "mcp"]


class QueryWorkIqParams(BaseModel):
    query: str = Field(
        description=(
            "Natural language question about the user's Microsoft 365 data. "
            "Examples: 'What did my manager say about the deadline?', "
            "'Find my recent documents about Q4 planning', "
            "'What are my meetings this week?'"
        )
    )
    data_type: str = Field(
        default="general",
        description=(
            "Type of M365 data to focus on: 'email', 'meetings', 'documents', "
            "'teams', 'people', or 'general'"
        ),
    )


@define_tool(
    description=(
        "Query the user's Microsoft 365 data (emails, meetings, Teams messages, "
        "documents, org chart) using Work IQ MCP. Use this tool when the user's "
        "organizational context, recent communications, or enterprise documents "
        "are relevant to diagnosing the support issue. "
        "IMPORTANT: Only use when explicitly relevant — this accesses private M365 data."
    )
)
async def query_workiq_tool(params: QueryWorkIqParams) -> str:
    """Query M365 data via the Work IQ MCP server."""
    if not _WORKIQ_ENABLED:
        return (
            "[Work IQ] Work IQ integration is disabled. "
            "Set WORKIQ_ENABLED=true in your environment and ensure the Work IQ MCP "
            "server is configured to enable M365 data access.\n"
            "Setup: npm install -g @microsoft/workiq && workiq login"
        )

    result = await _query_via_mcp_server(params.query)
    return result or (
        "[Work IQ] No results returned. Verify that:\n"
        "1. Work IQ is authenticated: run `workiq login`\n"
        "2. Your Microsoft 365 tenant admin has granted consent\n"
        "3. The Work IQ MCP server is reachable"
    )


async def _query_via_mcp_server(query: str) -> str | None:
    """Invoke the Work IQ MCP server via JSON-RPC over stdio."""
    try:
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
                "name": "ask",
                "arguments": {"question": query},
            },
        })

        proc = await asyncio.create_subprocess_exec(
            *_MCP_SERVER_CMD,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, _ = await asyncio.wait_for(
            proc.communicate(input=(init_req + "\n" + tool_req + "\n").encode()),
            timeout=60,
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
        logger.warning("Work IQ MCP server error: %s", exc)

    return None
