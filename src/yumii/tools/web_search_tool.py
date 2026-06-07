"""Web search tool for Yumii using LangChain.

A native LangChain tool that performs web searches using DuckDuckGoSearchResults,
registered on the global :data:`yumii.tools.registry.registry` with an EXTERNAL
policy (no API key required, confirmation gate recommended).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from yumii.core.logging import get_logger
from yumii.tools.policy import ToolCategory, ToolPolicy
from yumii.tools.registry import register

log = get_logger(__name__)


class WebSearchInput(BaseModel):
    """Input schema for web search.

    Attributes:
        query: The search query to send to the web search engine.
    """

    query: str = Field(
        ...,
        description=(
            "The search query to execute. Be specific and concise for "
            "better results. Examples: 'Python latest features 2024', "
            "'weather in Tokyo', 'stock market trends'."
        ),
    )


def _create_web_search_tool():
    """Initialize and return the DuckDuckGo web search tool.

    Returns:
        DuckDuckGoSearchResults tool instance, or None if import fails.
    """
    try:
        from langchain_community.tools import DuckDuckGoSearchResults

        tool = DuckDuckGoSearchResults()
        return tool
    except ImportError:
        log.warning(
            "langchain-community and/or ddgs not installed. "
            "Web search tool will not be registered. "
            "Install with: uv pip install ddgs langchain-community"
        )
        return None
    except Exception as e:
        log.error(f"Failed to initialize web search tool: {e}")
        return None


# Initialize the web search tool
_web_search_tool = _create_web_search_tool()

# Register on the global registry only if the tool was successfully created
if _web_search_tool is not None:
    register(
        _web_search_tool,
        ToolPolicy(
            category=ToolCategory.EXTERNAL,
            requires_confirmation=True,
            description_override=(
                "Search the web for current information using DuckDuckGo. "
                "Use when you need real-time data, news, or information not in your training data."
            ),
        ),
    )
    log.debug("Web search tool registered successfully")


__all__ = ["WebSearchInput"]
