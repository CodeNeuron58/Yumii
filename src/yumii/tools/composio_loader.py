"""Loads Composio tools for the user's enabled toolkits.

The user flow (documented end-to-end in Trash/composio_integration_journey.md):

1. The user pastes their Composio API key (Dashboard → Settings, stored
   in ``auth.json`` as ``COMPOSIO_API_KEY``).
2. They connect an app from the Dashboard's Tools panel: the backend
   mints an auth config and an OAuth link (``/api/composio/connect``),
   the browser opens it, they authenticate, and Composio holds the
   tokens server-side.
3. The enabled toolkit slugs live under ``COMPOSIO_TOOLKITS`` in
   ``~/.yumii/config.json``. On engine startup this module fetches
   those toolkits' tools and registers them on the global registry.

Safety default: every Composio tool is ``EXTERNAL`` with
``requires_confirmation=True`` — Yumii asks before acting on the
user's accounts, until they relax ``HITL_MODE`` themselves.

The Composio SDK is synchronous; all calls run in a worker thread.
This module never raises — failures are logged and boot continues.
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable

from yumii.core.config import settings
from yumii.core.global_config import load_global_config
from yumii.core.logging import get_logger
from yumii.tools.policy import ToolCategory, ToolPolicy
from yumii.tools.registry import registry

log = get_logger(__name__)

# Generous: Composio fetches tool schemas for every tool in a toolkit
# (Gmail alone is ~20 tools).
_LOAD_TIMEOUT_SEC = 60.0

USER_ID = "default"  # single-user app; one local user per install

_COMPOSIO_POLICY = ToolPolicy(
    category=ToolCategory.EXTERNAL,
    requires_confirmation=True,
)


def composio_api_key() -> str | None:
    """The Composio key, read fresh from auth.json.

    Fresh (not the boot-time ``settings`` snapshot) so that pasting the
    key in the dashboard and connecting an app works in the same
    session, without a backend restart.
    """
    from yumii.core.credential_store import get_credential

    return get_credential("COMPOSIO_API_KEY") or settings.composio_api_key


def get_composio_client() -> Any:
    """Build a Composio client with the LangChain provider.

    composio 0.13.x shape (see the journey doc §3): both ``api_key``
    and ``provider`` are constructor kwargs.
    """
    from composio import Composio
    from composio_langchain import LangchainProvider

    return Composio(api_key=composio_api_key(), provider=LangchainProvider())


def enabled_toolkits() -> list[str]:
    """Return the enabled toolkit slugs (upper-case) from config.json."""
    raw = load_global_config().get("COMPOSIO_TOOLKITS", [])
    if not isinstance(raw, list):
        return []
    return [str(t).upper() for t in raw if isinstance(t, str) and t.strip()]


async def load_and_register_composio_tools(
    client_factory: Callable[[], Any] | None = None,
) -> list[str]:
    """Fetch tools for every enabled toolkit and register them.

    Args:
        client_factory: Test seam — anything whose ``tools.get`` matches
            the Composio SDK. Defaults to :func:`get_composio_client`.

    Returns:
        The names of the tools that were registered.
    """
    if not composio_api_key():
        return []
    toolkits = enabled_toolkits()
    if not toolkits:
        return []

    factory = client_factory or get_composio_client

    def _load() -> list[Any]:
        client = factory()
        return client.tools.get(user_id=USER_ID, toolkits=toolkits)

    try:
        tools = await asyncio.wait_for(
            asyncio.to_thread(_load), timeout=_LOAD_TIMEOUT_SEC
        )
    except asyncio.TimeoutError:
        log.warning("composio_load_timeout", toolkits=toolkits, timeout=_LOAD_TIMEOUT_SEC)
        return []
    except Exception as e:
        log.warning("composio_load_failed", toolkits=toolkits, error=str(e))
        return []

    registered: list[str] = []
    for tool in tools:
        if tool.name in registry:
            log.warning("composio_tool_collision_skipped", tool=tool.name)
            continue
        registry.register(tool, _COMPOSIO_POLICY)
        registered.append(tool.name)

    log.info("composio_tools_registered", toolkits=toolkits, count=len(registered))
    return registered
