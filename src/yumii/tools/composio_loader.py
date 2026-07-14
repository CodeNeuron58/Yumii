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

# Curated per-toolkit tool subsets — applied ONLY on free-tier-capped
# providers (Groq). Loading a whole toolkit ships every tool's JSON
# schema with EVERY LLM request — measured: the full GMAIL toolkit is
# ~10k tokens of schema, which alone blows a free-tier Groq request
# (12k TPM cap) before the user says a word. Providers with real
# context windows (Ollama Cloud's minimax-m3: 1M) load full toolkits —
# the curated 2-tool Gmail was why "reply to that email" had no tool
# to call. Users can override per toolkit via COMPOSIO_TOOLS in
# config.json:
#   "COMPOSIO_TOOLS": {"GMAIL": ["GMAIL_FETCH_EMAILS", ...]}
_CURATED_TOOLS: dict[str, list[str]] = {
    # Two tools, not four: free-tier request ceilings are tiny (qwen:
    # 8k tokens TOTAL per request; llama: 12k) and each Gmail schema
    # costs ~1k tokens on every single turn.
    "GMAIL": [
        "GMAIL_FETCH_EMAILS",
        "GMAIL_SEND_EMAIL",
    ],
}

# Toolkits fetched whole still get a bound, not a firehose.
_UNCURATED_LIMIT = 8  # tight providers (Groq)
_FULL_TOOLKIT_LIMIT = 100  # everyone else — covers any real toolkit

# Names this loader registered on the global registry. Lets a runtime
# reload (user connects an app in the dashboard) replace the Composio
# tools cleanly without touching the native ones.
_registered_composio_tools: set[str] = set()


def _should_curate() -> bool:
    """Curated subsets only make sense under free-tier request caps."""
    return settings.llm_provider.lower() == "groq"


def _resolve_tool_selection(
    toolkits: list[str], overrides: dict | None, curate: bool = True
) -> tuple[list[str], list[str]]:
    """Split enabled toolkits into (explicit tool slugs, whole toolkits).

    Order of precedence per toolkit: user override from config.json,
    then — when ``curate`` — the curated default, else the toolkit is
    fetched whole (with a sanity limit).
    """
    overrides = overrides if isinstance(overrides, dict) else {}
    slugs: list[str] = []
    whole: list[str] = []
    for tk in toolkits:
        chosen = overrides.get(tk) or (_CURATED_TOOLS.get(tk) if curate else None)
        if isinstance(chosen, list) and chosen:
            slugs.extend(str(s).upper() for s in chosen)
        else:
            whole.append(tk)
    return slugs, whole


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
    # Reload-safe: drop whatever this loader registered last time, so a
    # runtime reload (dashboard connect/disable) replaces the Composio
    # tool set instead of erroring on collisions or leaving stale tools.
    for name in _registered_composio_tools:
        registry.unregister(name)
    _registered_composio_tools.clear()

    if not composio_api_key():
        return []
    toolkits = enabled_toolkits()
    if not toolkits:
        return []

    factory = client_factory or get_composio_client
    overrides = load_global_config().get("COMPOSIO_TOOLS")
    curate = _should_curate()
    slugs, whole = _resolve_tool_selection(toolkits, overrides, curate=curate)
    fetch_limit = _UNCURATED_LIMIT if curate else _FULL_TOOLKIT_LIMIT

    def _load() -> list[Any]:
        client = factory()
        loaded: list[Any] = []
        if slugs:
            loaded.extend(client.tools.get(user_id=USER_ID, tools=slugs))
        for tk in whole:
            loaded.extend(
                client.tools.get(
                    user_id=USER_ID, toolkits=[tk], limit=fetch_limit
                )
            )
        return loaded

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
        _registered_composio_tools.add(tool.name)
        registered.append(tool.name)

    log.info(
        "composio_tools_registered",
        toolkits=toolkits,
        count=len(registered),
        curated=curate,
    )
    return registered
