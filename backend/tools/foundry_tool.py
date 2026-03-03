"""
Azure AI Foundry Deep Research Tool.

Calls an Azure AI Foundry agent configured with DeepResearchTool and
Bing grounding to perform multi-step web research on a technical topic.
"""
from __future__ import annotations

import os
import logging
from pydantic import BaseModel, Field
from copilot import define_tool

logger = logging.getLogger(__name__)


class FoundryDeepResearchParams(BaseModel):
    query: str = Field(description="The technical question or research topic to investigate")
    context: str = Field(
        default="",
        description="Optional additional context to help focus the research",
    )


@define_tool(
    description=(
        "Perform deep technical research using Azure AI Foundry's research agent with "
        "Bing grounding. Use this tool for complex multi-step investigations, external "
        "web searches, and aggregating findings from multiple sources. Best for questions "
        "that require browsing up-to-date external documentation or Microsoft resources."
    )
)
async def foundry_deep_research_tool(params: FoundryDeepResearchParams) -> str:
    """Invoke the Azure AI Foundry Deep Research agent."""
    endpoint = os.environ.get("AZURE_FOUNDRY_PROJECT_ENDPOINT")
    model = os.environ.get("AZURE_FOUNDRY_DEEP_RESEARCH_MODEL")
    bing_resource = os.environ.get("AZURE_FOUNDRY_BING_RESOURCE")

    if not endpoint or not model:
        return (
            "[Foundry Deep Research] Azure AI Foundry is not configured. "
            "Set AZURE_FOUNDRY_PROJECT_ENDPOINT and AZURE_FOUNDRY_DEEP_RESEARCH_MODEL "
            "environment variables to enable this tool. "
            f"Returning placeholder for query: {params.query}"
        )

    try:
        from azure.identity import DefaultAzureCredential
        from azure.ai.projects import AIProjectClient
        from azure.ai.agents.models import DeepResearchTool, MessageRole

        credential = DefaultAzureCredential()
        project_client = AIProjectClient(credential=credential, endpoint=endpoint)
        agents_client = project_client.agents

        tools = []
        if bing_resource:
            tools.append(DeepResearchTool(bing_grounding_connection_name=bing_resource))

        agent = agents_client.create_agent(
            model=model,
            name="deep-research-agent",
            instructions=(
                "You are a deep research assistant specializing in Microsoft technologies. "
                "Conduct thorough research on the given topic, synthesize findings from "
                "multiple sources, and provide a comprehensive technical analysis."
            ),
            tools=[t.definitions[0] for t in tools] if tools else [],
            tool_resources={k: v for t in tools for k, v in t.resources.items()} if tools else {},
        )

        thread = agents_client.create_thread()
        agents_client.create_message(
            thread_id=thread.id,
            role=MessageRole.USER,
            content=f"{params.query}\n\nAdditional context: {params.context}" if params.context else params.query,
        )

        run = agents_client.create_and_process_run(thread_id=thread.id, agent_id=agent.id)

        if run.status == "failed":
            logger.error("Foundry run failed: %s", run.last_error)
            return f"[Foundry Deep Research] Research run failed: {run.last_error}"

        messages = agents_client.list_messages(thread_id=thread.id)
        result_parts = []
        for msg in messages.data:
            if msg.role == MessageRole.ASSISTANT:
                for content in msg.content:
                    if hasattr(content, "text"):
                        result_parts.append(content.text.value)

        agents_client.delete_agent(agent.id)

        return "\n\n".join(result_parts) if result_parts else "[Foundry] No results returned."

    except ImportError:
        return (
            "[Foundry Deep Research] azure-ai-projects package not installed. "
            "Run: pip install azure-ai-projects azure-identity"
        )
    except Exception as exc:
        logger.exception("Foundry deep research failed")
        return f"[Foundry Deep Research] Error: {exc}"
