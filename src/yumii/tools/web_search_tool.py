"""web_search — DuckDuckGo via the ddgs package (free, keyless), EXTERNAL policy.

Modeled on Hermes Agent's ddgs provider: the blocking search runs in a
disposable worker thread under a hard wall-clock timeout, failures come
back as plain text the model can voice, and results are normalized.
"""

from __future__ import annotations

import concurrent.futures as _cf

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from yumii.core.logging import get_logger
from yumii.tools.policy import ToolCategory, ToolPolicy
from yumii.tools.registry import register

log = get_logger(__name__)

# ddgs's multi-engine retry loop has no overall cap — a rate-limited scrape
# would otherwise hang the whole turn.
_SEARCH_TIMEOUT_SEC = 20
_MAX_RESULTS = 5
_SNIPPET_CHARS = 300


class WebSearchInput(BaseModel):
    """Input schema for web search."""

    query: str = Field(
        ...,
        description=(
            "The search query to execute. Be specific and concise for "
            "better results. Examples: 'Python latest features 2024', "
            "'weather in Tokyo', 'stock market trends'."
        ),
    )


def _run_search(query: str, limit: int) -> list[dict]:
    """Blocking ddgs query → normalized hits. Runs in a worker thread."""
    from ddgs import DDGS

    hits: list[dict] = []
    with DDGS(timeout=10) as client:
        for i, hit in enumerate(client.text(query, max_results=limit)):
            if i >= limit:
                break
            hits.append(
                {
                    "title": str(hit.get("title", "")).strip(),
                    "url": str(hit.get("href") or hit.get("url") or "").strip(),
                    "snippet": str(hit.get("body", "")).strip(),
                }
            )
    return hits


def _format_results(query: str, hits: list[dict]) -> str:
    if not hits:
        return (
            f"No results found for '{query}'. It may have been phrased "
            "unusually — try different words."
        )
    lines = [f"Top web results for '{query}':"]
    for i, h in enumerate(hits, 1):
        lines.append(f"{i}. {h['title']}\n   {h['snippet'][:_SNIPPET_CHARS]}\n   ({h['url']})")
    return "\n".join(lines)


@tool("web_search", args_schema=WebSearchInput)
def web_search(query: str) -> str:
    """Search the web for current information — news, facts, weather, prices,
    anything newer than your training data.

    Use when the user asks about something recent or outside your knowledge.
    Returns the top results with titles, snippets, and URLs — tell the user
    what you found in your own words, and never read URLs aloud.
    """
    query = (query or "").strip()
    if not query:
        return "Empty search query — say what to look for."

    # Fresh single-worker pool per call: a timed-out ddgs call can't be
    # cancelled, and a shared pool would queue every later search behind it.
    pool = _cf.ThreadPoolExecutor(max_workers=1)
    try:
        future = pool.submit(_run_search, query, _MAX_RESULTS)
        try:
            hits = future.result(timeout=_SEARCH_TIMEOUT_SEC)
        except _cf.TimeoutError:
            log.warning("web_search_timeout", query=query[:80], timeout=_SEARCH_TIMEOUT_SEC)
            return (
                "The web search timed out — the search engine may be "
                "rate-limiting right now. Try again in a little while."
            )
        except Exception as exc:
            log.warning("web_search_failed", query=query[:80], error=str(exc))
            return f"The web search failed: {exc}"
    finally:
        # Abandon a hung worker instead of joining it; it shares no state.
        pool.shutdown(wait=False, cancel_futures=True)

    log.info("web_search_done", query=query[:80], results=len(hits))
    return _format_results(query, hits)


try:
    import ddgs  # noqa: F401

    register(
        web_search,
        ToolPolicy(
            category=ToolCategory.EXTERNAL,
            requires_confirmation=True,
        ),
    )
except ImportError:
    log.warning(
        "ddgs not installed — web search tool not registered. "
        "Install with: uv add ddgs"
    )


__all__ = ["WebSearchInput", "web_search"]
