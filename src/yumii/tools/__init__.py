"""Tool package — importing it registers the built-in get_current_time tool.

The registry singleton is re-exported as ``global_registry`` to avoid shadowing
the ``yumii.tools.registry`` submodule.
"""

from __future__ import annotations

from yumii.tools.policy import (
    DEFAULT_POLICIES,
    ToolCategory,
    ToolPolicy,
    default_policy_for,
)
from yumii.tools.registry import (
    ToolRegistry,
    bind_to_llm,
    get,
    get_policy,
    list_policies,
    list_tools,
    register,
    register_many,
    registry as global_registry,
)
from yumii.tools.memory_tool import (  # noqa: F401
    ManageMemoryInput,
    manage_memory,
)
from yumii.tools.session_search_tool import (  # noqa: F401
    RecallInput,
    search_past_conversations,
)
from yumii.tools.time_tool import TimeInput, get_current_time
from yumii.tools.web_search_tool import WebSearchInput  # noqa: F401

__all__ = [
    # Registry
    "ToolRegistry",
    "global_registry",
    "register",
    "register_many",
    "get",
    "get_policy",
    "list_tools",
    "list_policies",
    "bind_to_llm",
    # Policy
    "ToolCategory",
    "ToolPolicy",
    "DEFAULT_POLICIES",
    "default_policy_for",
    # Built-in tools
    "TimeInput",
    "get_current_time",
    "WebSearchInput",
    "RecallInput",
    "search_past_conversations",
    "ManageMemoryInput",
    "manage_memory",
]
