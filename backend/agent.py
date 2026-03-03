"""
Support Agent — Copilot SDK orchestrator.

Manages the lifecycle of GitHub Copilot SDK sessions and registers
all custom tools (Foundry deep research, PowerPoint, MS Docs, Work IQ).
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, AsyncIterator, Dict, Optional

from copilot import CopilotClient

from tools import (
    foundry_deep_research_tool,
    generate_powerpoint_tool,
    query_ms_docs_tool,
    query_workiq_tool,
)
from skills import SUPPORT_INVESTIGATION_SYSTEM_MESSAGE

logger = logging.getLogger(__name__)


def _build_byok_provider() -> Dict[str, Any]:
    """Build a BYOK provider config from environment variables."""
    provider_type = os.environ.get("BYOK_PROVIDER", "openai")
    base_url = os.environ.get("BYOK_BASE_URL", "")
    api_key = os.environ.get("BYOK_API_KEY", "")
    config: Dict[str, Any] = {
        "type": provider_type,
        "base_url": base_url,
    }
    if api_key:
        config["api_key"] = api_key
    if provider_type == "azure":
        config["azure"] = {
            "api_version": os.environ.get("BYOK_AZURE_API_VERSION", "2024-10-21")
        }
    return config


def _build_client() -> CopilotClient:
    """Create a CopilotClient, supporting both GitHub auth and BYOK."""
    github_token = os.environ.get("COPILOT_GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    cli_path = os.environ.get("COPILOT_CLI_PATH", "copilot")

    # BYOK configuration (no GitHub subscription needed)
    byok_provider = os.environ.get("BYOK_PROVIDER")
    if byok_provider:
        logger.info("Using BYOK provider: %s", byok_provider)

    client_opts: Dict[str, Any] = {
        "cli_path": cli_path,
        "log_level": os.environ.get("LOG_LEVEL", "warning"),
        "auto_restart": True,
    }
    if github_token:
        client_opts["github_token"] = github_token

    return CopilotClient(client_opts)


class SupportAgent:
    """
    Wraps the GitHub Copilot SDK to provide a multi-tool support agent.

    One shared CopilotClient is created per application instance.
    Individual chat conversations each get their own CopilotSession.
    """

    def __init__(self) -> None:
        self._client: Optional[CopilotClient] = None
        self._sessions: Dict[str, Any] = {}
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Start the underlying Copilot CLI server."""
        self._client = _build_client()
        await self._client.start()
        logger.info("Copilot SDK client started.")

    async def stop(self) -> None:
        """Shut down all sessions and the CLI server."""
        for session in list(self._sessions.values()):
            try:
                await session.destroy()
            except Exception:
                pass
        self._sessions.clear()
        if self._client:
            await self._client.stop()
        logger.info("Copilot SDK client stopped.")

    async def list_models(self) -> list[dict]:
        """Return models available via the Copilot CLI."""
        if not self._client:
            return []
        try:
            models = await self._client.list_models()
            return [{"id": m.id, "name": getattr(m, "display_name", m.id)} for m in models]
        except Exception as exc:
            logger.warning("Could not list models: %s", exc)
            return [
                {"id": "gpt-4o", "name": "GPT-4o"},
                {"id": "gpt-4.1", "name": "GPT-4.1"},
                {"id": "claude-sonnet-4-5", "name": "Claude Sonnet 4.5"},
                {"id": "o4-mini", "name": "o4-mini"},
            ]

    async def get_or_create_session(self, session_id: str, model: str) -> Any:
        """Get an existing session or create a new one for the given ID."""
        async with self._lock:
            if session_id in self._sessions:
                return self._sessions[session_id]

            byok_provider = os.environ.get("BYOK_PROVIDER")
            session_config: Dict[str, Any] = {
                "session_id": session_id,
                "model": model,
                "streaming": True,
                "system_message": {"content": SUPPORT_INVESTIGATION_SYSTEM_MESSAGE},
                "tools": [
                    query_ms_docs_tool,
                    foundry_deep_research_tool,
                    query_workiq_tool,
                    generate_powerpoint_tool,
                ],
            }

            if byok_provider:
                session_config["provider"] = _build_byok_provider()

            session = await self._client.create_session(session_config)
            self._sessions[session_id] = session
            logger.info("Created session %s (model=%s)", session_id, model)
            return session

    async def send_message(
        self,
        session_id: str,
        prompt: str,
        model: str = "gpt-4o",
    ) -> AsyncIterator[dict]:
        """
        Send a message to a session and yield SSE-style event dicts.

        Yields dicts with shape:
          {"type": "assistant.message_delta", "content": "..."}
          {"type": "tool.execution_start", "tool_name": "...", "args": {...}}
          {"type": "tool.execution_complete", "tool_name": "...", "result": "..."}
          {"type": "assistant.message", "content": "..."}
          {"type": "session.idle"}
          {"type": "error", "message": "..."}
        """
        queue: asyncio.Queue[dict | None] = asyncio.Queue()

        async def _run() -> None:
            try:
                session = await self.get_or_create_session(session_id, model)
                done_event = asyncio.Event()

                def on_event(event: Any) -> None:
                    evt_type = event.type.value if hasattr(event.type, "value") else str(event.type)
                    data = event.data if hasattr(event, "data") else {}

                    if evt_type == "assistant.message_delta":
                        queue.put_nowait({
                            "type": "assistant.message_delta",
                            "content": getattr(data, "delta_content", "") or "",
                        })
                    elif evt_type == "assistant.message":
                        queue.put_nowait({
                            "type": "assistant.message",
                            "content": getattr(data, "content", "") or "",
                        })
                    elif evt_type == "tool.execution_start":
                        queue.put_nowait({
                            "type": "tool.execution_start",
                            "tool_name": getattr(data, "tool_name", "unknown"),
                            "args": getattr(data, "tool_args", {}),
                        })
                    elif evt_type == "tool.execution_complete":
                        result = getattr(data, "result", None)
                        queue.put_nowait({
                            "type": "tool.execution_complete",
                            "tool_name": getattr(data, "tool_name", "unknown"),
                            "result": str(result) if result is not None else "",
                        })
                    elif evt_type == "session.idle":
                        queue.put_nowait({"type": "session.idle"})
                        queue.put_nowait(None)  # sentinel
                        done_event.set()

                unsubscribe = session.on(on_event)
                try:
                    await session.send({"prompt": prompt})
                    # Wait up to 5 minutes for session.idle
                    await asyncio.wait_for(done_event.wait(), timeout=300)
                except asyncio.TimeoutError:
                    queue.put_nowait({"type": "error", "message": "Request timed out."})
                    queue.put_nowait(None)
                finally:
                    unsubscribe()

            except Exception as exc:
                logger.exception("Error in send_message")
                queue.put_nowait({"type": "error", "message": str(exc)})
                queue.put_nowait(None)

        asyncio.create_task(_run())

        while True:
            item = await queue.get()
            if item is None:
                break
            yield item

    async def delete_session(self, session_id: str) -> None:
        """Destroy and remove a session."""
        async with self._lock:
            session = self._sessions.pop(session_id, None)
        if session:
            await session.destroy()
            logger.info("Deleted session %s", session_id)
