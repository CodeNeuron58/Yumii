"""External tools and utilities for Yumii's reasoning engine.

Importing this package registers the built-in :func:`get_current_time`
tool on the global registry. The MCP loader is a separate
:func:`yumii.tools.mcp_config.load_mcp_servers` call so projects that
don't use MCP don't pay the import cost.

Note on the ``registry`` re-export: we import the singleton under
the name ``global_registry`` to avoid shadowing the submodule
``yumii.tools.registry``. A bare ``import yumii.tools.registry`` would
otherwise resolve to the ``ToolRegistry`` *instance* (because
``yumii.tools.__init__`` binds that name), which breaks
``yumii.tools.registry.list_tools()`` and similar submodule-style
access. Callers should prefer ``from yumii.tools.registry import
registry as global_registry`` (as the tests do).
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
