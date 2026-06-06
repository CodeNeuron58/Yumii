"""External tools and utilities for Yumii's reasoning engine.

Importing this package registers the built-in :func:`get_current_time`
tool on the global registry. The MCP loader is a separate
:func:`yumii.tools.mcp_config.load_mcp_servers` call so projects that
don't use MCP don't pay the import cost.
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
    registry,
)
from yumii.tools.time_tool import TimeInput, get_current_time

__all__ = [
    # Registry
    "ToolRegistry",
    "registry",
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
]
