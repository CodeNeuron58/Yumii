"""Connects configured MCP servers and registers their tools.

Reads the ``MCP_SERVERS`` list from ``~/.yumii/config.json`` (parsed by
:mod:`yumii.tools.mcp_config`), connects each server through
``langchain-mcp-adapters``, and registers the resulting tools on the
global registry.

Safety default: every MCP tool gets ``ToolCategory.EXTERNAL`` with
``requires_confirmation=True``, so it triggers the HITL gate — Yumii
asks before touching the outside world — until the user relaxes
``HITL_MODE`` themselves.

Resilience: one client per server, each with a connect timeout, so a
dead or misconfigured server is logged and skipped without blocking
boot or breaking the other servers. This module never raises.
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable

from yumii.core.logging import get_logger
from yumii.tools.mcp_config import load_mcp_servers
from yumii.tools.policy import ToolCategory, ToolPolicy
from yumii.tools.registry import registry

log = get_logger(__name__)

# Generous because stdio servers may install packages on first run
# (npx/uvx download the server the first time).
_CONNECT_TIMEOUT_SEC = 30.0

_MCP_POLICY = ToolPolicy(
    category=ToolCategory.EXTERNAL,
    requires_confirmation=True,
)


async def load_and_register_mcp_tools(
    client_factory: Callable[[dict], Any] | None = None,
) -> list[str]:
    """Connect every configured MCP server and register its tools.

    Args:
        client_factory: Test seam — anything that accepts the
            ``{name: connection}`` dict and exposes ``get_tools()``.
            Defaults to ``MultiServerMCPClient``.

    Returns:
        The names of the tools that were registered.
    """
    servers = load_mcp_servers()
    if not servers:
        return []

    if client_factory is None:
        from langchain_mcp_adapters.client import MultiServerMCPClient

        client_factory = MultiServerMCPClient

    registered: list[str] = []
    for cfg in servers:
        try:
            client = client_factory({cfg.name: cfg.to_adapter_dict()})
            tools = await asyncio.wait_for(
                client.get_tools(), timeout=_CONNECT_TIMEOUT_SEC
            )
        except asyncio.TimeoutError:
            log.warning(
                "mcp_server_timeout", server=cfg.name, timeout=_CONNECT_TIMEOUT_SEC
            )
            continue
        except Exception as e:
            log.warning("mcp_server_connect_failed", server=cfg.name, error=str(e))
            continue

        names: list[str] = []
        for tool in tools:
            if tool.name in registry:
                # Native tools and earlier servers win; skipping keeps
                # the registry unambiguous for the LLM.
                log.warning(
                    "mcp_tool_collision_skipped", server=cfg.name, tool=tool.name
                )
                continue
            registry.register(tool, _MCP_POLICY)
            names.append(tool.name)

        registered.extend(names)
        log.info("mcp_server_connected", server=cfg.name, tools=names)

    return registered
