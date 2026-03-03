"""
Azure AI Foundry Deep Research Tool.

Uses the Foundry V2 (Azure AI Projects 2.x) agent API with Web Search
to perform multi-step web research on a technical topic.
"""
from __future__ import annotations

import os
import logging
from typing import Any, Optional
from pydantic import BaseModel, Field
from copilot import define_tool

from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
	PromptAgentDefinition,
	WebSearchTool,
	WebSearchApproximateLocation,
)

logger = logging.getLogger(__name__)
_cached_agent: Optional[dict[str, Any]] = None


class FoundryDeepResearchParams(BaseModel):
    query: str = Field(description="The technical question or research topic to investigate")
    context: str = Field(
        default="",
        description="Optional additional context to help focus the research",
    )

def _get_or_create_agent(
    project_client: AIProjectClient,
    agent_name: str,
    definition: PromptAgentDefinition,
) -> dict[str, Any]:
    global _cached_agent
    if _cached_agent and _cached_agent.get("name") == agent_name:
        return _cached_agent

    agent = None
    get_agent = getattr(project_client.agents, "get", None)
    if callable(get_agent):
        try:
            agent = get_agent(agent_name=agent_name)
        except TypeError:
            agent = get_agent(agent_name)
        except Exception:
            agent = None

    if agent is None:
        agent = project_client.agents.create_version(
            agent_name=agent_name,
            definition=definition,
            description="Agent for web search.",
        )

    _cached_agent = {
        "id": getattr(agent, "id", None),
        "name": getattr(agent, "name", agent_name),
        "version": getattr(agent, "version", None),
    }
    return _cached_agent

@define_tool(
    description=(
        "Perform deep technical research using Azure AI Foundry's research agent with "
        "Web Search. Use this tool for complex multi-step investigations, external "
        "web searches, and aggregating findings from multiple sources. Best for questions "
        "that require browsing up-to-date external documentation or Microsoft resources."
    )
)
async def foundry_deep_research_tool(params: FoundryDeepResearchParams) -> str:
    """Invoke the Azure AI Foundry Deep Research agent."""
    endpoint = (
        os.environ.get("FOUNDRY_PROJECT_ENDPOINT")
        or os.environ.get("PROJECT_ENDPOINT")
        or os.environ.get("AZURE_FOUNDRY_PROJECT_ENDPOINT")
    )
    model = (
        os.environ.get("FOUNDRY_MODEL_DEPLOYMENT_NAME")
        or os.environ.get("MODEL_DEPLOYMENT_NAME")
        or os.environ.get("AZURE_FOUNDRY_DEEP_RESEARCH_MODEL")
    )
    agent_name = (
        os.environ.get("AGENT_NAME")
        or os.environ.get("AZURE_FOUNDRY_AGENT_NAME")
        or "deep-research-agent"
    )
    search_context_size = os.environ.get("FOUNDRY_WEB_SEARCH_CONTEXT_SIZE", "medium")
    search_country = os.environ.get("FOUNDRY_WEB_SEARCH_COUNTRY")
    search_region = os.environ.get("FOUNDRY_WEB_SEARCH_REGION")
    search_city = os.environ.get("FOUNDRY_WEB_SEARCH_CITY")

    if not endpoint or not model:
        return (
            "[Foundry Deep Research] Azure AI Foundry is not configured. "
            "Set FOUNDRY_PROJECT_ENDPOINT and FOUNDRY_MODEL_DEPLOYMENT_NAME "
            "(or PROJECT_ENDPOINT and MODEL_DEPLOYMENT_NAME) "
            "environment variables to enable this tool. "
            f"Returning placeholder for query: {params.query}"
        )

    try:

        with (
            DefaultAzureCredential() as credential,
            AIProjectClient(credential=credential, endpoint=endpoint) as project_client,
            project_client.get_openai_client() as openai_client,
        ):
            tools = [
                WebSearchTool(
                    search_context_size=search_context_size,
                    user_location=(
                        WebSearchApproximateLocation(
                            country=search_country,
                            region=search_region,
                            city=search_city,
                        )
                        if search_country or search_region or search_city
                        else None
                    ),
                )
            ]

            definition = PromptAgentDefinition(
                model=model,
                instructions=(
                    "You are a deep research assistant specializing in Microsoft technologies. "
                    "Conduct thorough research on the given topic, synthesize findings from "
                    "multiple sources, and provide a comprehensive technical analysis."
                ),
                tools=tools or None,
            )

            agent = _get_or_create_agent(project_client, agent_name, definition)

            user_input = (
                f"{params.query}\n\nAdditional context: {params.context}"
                if params.context
                else params.query
            )
            response = openai_client.responses.create(
                tool_choice="required",
                input=user_input,
                extra_body={
                    "agent_reference": {"name": agent["name"], "type": "agent_reference"}
                },
            )

            return response.output_text or "[Foundry] No results returned."

    except ImportError:
        return (
            "[Foundry Deep Research] Azure AI Projects v2 package not installed. "
            "Run: pip install --pre \"azure-ai-projects>=2.0.0b4\" azure-identity"
        )
    except Exception as exc:
        logger.exception("Foundry deep research failed")
        return f"[Foundry Deep Research] Error: {exc}"
