"""
Tools package for the support agent.
"""
from .foundry_tool import foundry_deep_research_tool
from .pptx_tool import generate_powerpoint_tool
from .msdocs_tool import query_ms_docs_tool
from .workiq_tool import query_workiq_tool

__all__ = [
    "foundry_deep_research_tool",
    "generate_powerpoint_tool",
    "query_ms_docs_tool",
    "query_workiq_tool",
]
