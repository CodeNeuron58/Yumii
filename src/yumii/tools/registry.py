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

from typing import Iterable

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from yumii.core.logging import get_logger
from yumii.tools.policy import ToolPolicy

log = get_logger(__name__)


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

    def unregister(self, name: str) -> None:
        """Remove a single tool (no-op if absent).

        Used by runtime tool reloads (e.g. the Composio loader swapping
        its tool set after the user connects an app in the dashboard).
        """
        self._tools.pop(name, None)
        self._policies.pop(name, None)

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


def tools_requiring_confirmation() -> list[str]:
    """Return the names of tools that need a confirmation gate."""
    return registry.tools_requiring_confirmation()


def _make_null_defaults_nullable(node: dict) -> None:
    """In-place: let every null-defaulted property actually accept null.

    Composio (and other third-party) schemas declare optional fields as
    bare ``{"type": "string", "default": null}`` — not nullable. Llama
    models fill optionals with explicit ``null``, and Groq validates
    tool calls against the schema server-side, so the combination
    rejects semantically perfect calls with ``tool_use_failed``
    ("/query: expected string, but got null"). Widening the type to
    ``["string", "null"]`` makes the model's behaviour legal.
    """
    for prop in node.get("properties", {}).values():
        if not isinstance(prop, dict):
            continue
        if "default" in prop and prop["default"] is None:
            t = prop.get("type")
            if isinstance(t, str) and t != "null":
                prop["type"] = [t, "null"]
            elif isinstance(prop.get("anyOf"), list) and not any(
                isinstance(o, dict) and o.get("type") == "null"
                for o in prop["anyOf"]
            ):
                prop["anyOf"].append({"type": "null"})
        # Qwen-family models write tool calls in an XML dialect with
        # Python-cased booleans ("True"); Groq's parser forwards those
        # as strings and its validator then rejects the call. Accept
        # the string form — pydantic lax-coerces "True"/"false" back to
        # real booleans at execution time.
        if prop.get("type") == "boolean":
            prop["type"] = ["boolean", "string"]
        elif isinstance(prop.get("type"), list) and "boolean" in prop["type"] and "string" not in prop["type"]:
            prop["type"] = [*prop["type"], "string"]
        # Recurse into nested object schemas wherever they may hide.
        if isinstance(prop.get("properties"), dict):
            _make_null_defaults_nullable(prop)
        items = prop.get("items")
        if isinstance(items, dict) and isinstance(items.get("properties"), dict):
            _make_null_defaults_nullable(items)
        for branch in prop.get("anyOf", []) if isinstance(prop.get("anyOf"), list) else []:
            if isinstance(branch, dict):
                if isinstance(branch.get("properties"), dict):
                    _make_null_defaults_nullable(branch)
                nested_items = branch.get("items")
                if isinstance(nested_items, dict) and isinstance(
                    nested_items.get("properties"), dict
                ):
                    _make_null_defaults_nullable(nested_items)


def bind_to_llm(llm: BaseChatModel) -> BaseChatModel:
    """Bind the global registry's tools to an LLM via ``bind_tools``.

    Tools are bound as sanitized OpenAI-format schema dicts (see
    :func:`_make_null_defaults_nullable`) rather than raw ``BaseTool``
    objects — the LLM only needs names and schemas; the ``ToolNode``
    still dispatches to the registered tool objects by name.
    """
    from langchain_core.utils.function_calling import convert_to_openai_tool

    schemas = []
    for tool in list_tools():
        schema = convert_to_openai_tool(tool)
        _make_null_defaults_nullable(
            schema.get("function", {}).get("parameters", {})
        )
        schemas.append(schema)
    return llm.bind_tools(schemas)


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
