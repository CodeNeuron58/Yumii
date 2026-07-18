"""Load Composio tools for enabled toolkits (safe-by-default: every tool HITL-gated; boot never blocks)."""

from __future__ import annotations

import asyncio
from typing import Any, Callable

from yumii.core.config import settings
from yumii.core.global_config import load_global_config
from yumii.core.logging import get_logger
from yumii.tools.policy import ToolCategory, ToolPolicy
from yumii.tools.registry import registry

log = get_logger(__name__)

# Generous — Composio fetches schemas for every tool in a toolkit.
_LOAD_TIMEOUT_SEC = 60.0

USER_ID = "default"  # single-user app; one local user per install

_COMPOSIO_POLICY = ToolPolicy(
    category=ToolCategory.EXTERNAL,
    requires_confirmation=True,
)

# Curated subsets only on free-tier-capped providers (Groq): a full toolkit's schemas
# (~10k tokens) blow the request cap. Override per toolkit via COMPOSIO_TOOLS in config.json.
_CURATED_TOOLS: dict[str, list[str]] = {
    "GMAIL": [
        "GMAIL_FETCH_EMAILS",
        "GMAIL_SEND_EMAIL",
    ],
}

# Bound even when fetching a toolkit whole: tight providers (Groq) vs everyone else.
_UNCURATED_LIMIT = 8
_FULL_TOOLKIT_LIMIT = 100

# Names we registered — lets a reload replace only the Composio tools.
_registered_composio_tools: set[str] = set()


def _should_curate() -> bool:
    """Curated subsets only make sense under free-tier request caps."""
    return settings.llm_provider.lower() == "groq"


def _resolve_tool_selection(
    toolkits: list[str], overrides: dict | None, curate: bool = True
) -> tuple[list[str], list[str]]:
    """Split enabled toolkits into (explicit tool slugs, whole toolkits) by override/curated default."""
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
    """The Composio key, read fresh from auth.json (so pasting it works without a restart)."""
    from yumii.core.credential_store import get_credential

    return get_credential("COMPOSIO_API_KEY") or settings.composio_api_key


def get_composio_client() -> Any:
    """Build a Composio client (0.13.x: api_key + provider kwargs)."""
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
    """Fetch tools for every enabled toolkit and register them; returns the registered names."""
    # Reload-safe: drop what we registered last time before re-registering.
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
