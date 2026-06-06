"""Tool registry for Yumii's agent loop.

A single, uniform place to register tools regardless of where they came
from — a native ``@tool`` function defined in this codebase, a tool
returned by :class:`langchain_mcp_adapters.client.MultiServerMCPClient`,
or a hand-rolled ``BaseTool`` subclass. The registry stores the tool
plus its :class:`~yumii.tools.policy.ToolPolicy` and exposes the
combined list for the LangGraph ``ToolNode`` to execute.

The registry is a module-level singleton (see ``registry`` at the
bottom of this file). All access goes through helper functions so
tests can substitute their own instance.

Typical usage:

.. code-block:: python

    from langchain_core.tools import tool
    from yumii.tools.policy import ToolCategory, ToolPolicy
    from yumii.tools.registry import register, bind_to_llm

    @tool
    def get_weather(city: str) -> str:
        \"\"\"Get the weather for a city.\"\"\"
        return f\"Sunny in {city}\"

    register(get_weather, ToolPolicy(category=ToolCategory.EXTERNAL))

    # Later, in the agent:
    llm_with_tools = bind_to_llm(base_llm)
"""

from __future__ import annotations

import logging
from typing import Iterable

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from yumii.tools.policy import ToolPolicy

log = logging.getLogger(__name__)


class ToolRegistry:
    """In-memory store of tools + their policies.

    The registry is intentionally dumb: it has no LLM, no graph, no
    state. It just holds a ``{name: (BaseTool, ToolPolicy)}`` mapping
    and answers questions about it. The agent graph (``graph.py``) and
    the synthesizer (``synthesizer.py``) read from it; nothing else
    mutates it after startup.
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}
        self._policies: dict[str, ToolPolicy] = {}

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def register(
        self,
        tool: BaseTool,
        policy: ToolPolicy | None = None,
        *,
        overwrite: bool = False,
    ) -> None:
        """Register a tool with an optional policy.

        Args:
            tool: A LangChain ``BaseTool`` instance. This is what
                ``@tool`` returns, and what ``MultiServerMCPClient.get_tools()``
                returns for MCP-loaded tools.
            policy: The :class:`ToolPolicy` to associate with this tool.
                If None, defaults to a READ-category policy with no
                confirmation gate.
            overwrite: If False (the default), re-registering a tool
                with the same name raises ``ValueError``. This is a
                safety net against accidental shadowing in startup
                code. Set to True for tests that need to swap tools in
                and out.

        Raises:
            ValueError: If a tool with the same name is already
                registered and ``overwrite`` is False.
        """
        name = tool.name
        if not overwrite and name in self._tools:
            raise ValueError(
                f"Tool {name!r} is already registered. "
                "Pass overwrite=True to replace it, or use a "
                "different tool name."
            )
        self._tools[name] = tool
        self._policies[name] = policy or ToolPolicy()
        log.debug(
            "tool_registered",
            name=name,
            category=self._policies[name].category.value,
            requires_confirmation=self._policies[name].requires_confirmation,
        )

    def register_many(
        self,
        tools: Iterable[BaseTool],
        policies: dict[str, ToolPolicy] | None = None,
        *,
        overwrite: bool = False,
    ) -> None:
        """Register a batch of tools.

        Args:
            tools: Iterable of ``BaseTool`` instances.
            policies: Optional dict mapping tool name to its policy.
                Tools without an entry in ``policies`` get the default
                policy. If ``policies`` is None, all tools get the
                default policy.
            overwrite: Forwarded to :meth:`register`.
        """
        policies = policies or {}
        for tool in tools:
            self.register(tool, policies.get(tool.name), overwrite=overwrite)

    def clear(self) -> None:
        """Remove every registered tool. Intended for tests."""
        self._tools.clear()
        self._policies.clear()

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get(self, name: str) -> BaseTool:
        """Return the tool registered under ``name``.

        Raises:
            KeyError: If no tool is registered under that name.
        """
        if name not in self._tools:
            raise KeyError(
                f"No tool named {name!r}. "
                f"Known tools: {sorted(self._tools)}"
            )
        return self._tools[name]

    def get_policy(self, name: str) -> ToolPolicy:
        """Return the policy for the tool registered under ``name``.

        Raises:
            KeyError: If no tool is registered under that name.
        """
        if name not in self._policies:
            raise KeyError(
                f"No policy for tool {name!r}. "
                f"Known tools: {sorted(self._policies)}"
            )
        return self._policies[name]

    def list_tools(self) -> list[BaseTool]:
        """Return every registered tool. Order is registration order."""
        return list(self._tools.values())

    def list_policies(self) -> dict[str, ToolPolicy]:
        """Return ``{name: policy}`` for every registered tool."""
        return dict(self._policies)

    def tools_requiring_confirmation(self) -> list[str]:
        """Return the names of tools that need a confirmation gate."""
        return [
            name
            for name, policy in self._policies.items()
            if policy.requires_confirmation
        ]

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)


# ----------------------------------------------------------------------
# Module-level singleton + helper functions
# ----------------------------------------------------------------------

# All access from the rest of the codebase goes through this singleton.
# Tests that need isolation can call ``registry.clear()`` in a fixture.
registry = ToolRegistry()


def register(
    tool: BaseTool,
    policy: ToolPolicy | None = None,
    *,
    overwrite: bool = False,
) -> None:
    """Register a tool on the global registry. See :meth:`ToolRegistry.register`."""
    registry.register(tool, policy, overwrite=overwrite)


def register_many(
    tools: Iterable[BaseTool],
    policies: dict[str, ToolPolicy] | None = None,
    *,
    overwrite: bool = False,
) -> None:
    """Register a batch of tools on the global registry."""
    registry.register_many(tools, policies, overwrite=overwrite)


def get(name: str) -> BaseTool:
    """Return the tool registered under ``name`` on the global registry."""
    return registry.get(name)


def get_policy(name: str) -> ToolPolicy:
    """Return the policy for the tool registered under ``name``."""
    return registry.get_policy(name)


def list_tools() -> list[BaseTool]:
    """Return every registered tool."""
    return registry.list_tools()


def list_policies() -> dict[str, ToolPolicy]:
    """Return ``{name: policy}`` for every registered tool."""
    return registry.list_policies()


def bind_to_llm(llm: BaseChatModel) -> BaseChatModel:
    """Bind the global registry's tools to an LLM via ``bind_tools``.

    This is the only integration point between the registry and the
    LangChain ecosystem. The agent graph calls this once at startup
    and stores the result.
    """
    return llm.bind_tools(list_tools())


__all__ = [
    "ToolRegistry",
    "registry",
    "register",
    "register_many",
    "get",
    "get_policy",
    "list_tools",
    "list_policies",
    "bind_to_llm",
]
