"""web_search — Tavily when TAVILY_API_KEY is set, else DuckDuckGo (ddgs); EXTERNAL policy.

Tavily is built for agents: clean extracted content plus a short
synthesized answer, which suits a reply that is spoken aloud. Without a
key — or if Tavily fails — the free, keyless ddgs path answers instead.
Modeled on Hermes Agent's ddgs provider: the blocking search runs in a
disposable worker thread under a hard wall-clock timeout, failures come
back as plain text the model can voice, and results are normalized.
"""

from __future__ import annotations

import concurrent.futures as _cf
import json
import os
import urllib.request

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
_TAVILY_URL = "https://api.tavily.com/search"
_TAVILY_TIMEOUT_SEC = 15


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


def _run_tavily(query: str, limit: int, api_key: str) -> tuple[str | None, list[dict]]:
    """Blocking Tavily search → (short answer, normalized hits). Runs in a worker thread."""
    payload = json.dumps(
        {"query": query, "max_results": limit, "search_depth": "basic", "include_answer": True}
    ).encode("utf-8")
    request = urllib.request.Request(
        _TAVILY_URL,
        data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=_TAVILY_TIMEOUT_SEC) as resp:
        data = json.load(resp)
    hits = [
        {
            "title": str(h.get("title", "")).strip(),
            "url": str(h.get("url", "")).strip(),
            "snippet": str(h.get("content", "")).strip(),
        }
        for h in (data.get("results") or [])[:limit]
    ]
    answer = str(data.get("answer") or "").strip() or None
    return answer, hits


def _format_results(query: str, hits: list[dict], answer: str | None = None) -> str:
    if not hits and not answer:
        return (
            f"No results found for '{query}'. It may have been phrased "
            "unusually — try different words."
        )
    lines = []
    if answer:
        lines.append(f"Quick answer: {answer}")
    lines.append(f"Top web results for '{query}':")
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

    tavily_key = (os.environ.get("TAVILY_API_KEY") or "").strip()
    if tavily_key:
        pool = _cf.ThreadPoolExecutor(max_workers=1)
        try:
            answer, hits = pool.submit(_run_tavily, query, _MAX_RESULTS, tavily_key).result(
                timeout=_TAVILY_TIMEOUT_SEC + 2
            )
            log.info("web_search_done", engine="tavily", query=query[:80], results=len(hits))
            return _format_results(query, hits, answer)
        except Exception as exc:
            # Never the key, never raw internals — fall back to the free engine.
            log.warning("tavily_search_failed_falling_back", query=query[:80], error=type(exc).__name__)
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

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
            # A canned phrase — the tool result is spoken aloud, and raw
            # exception text would leak internals into her voice.
            return (
                "The web search failed on my end — the engine may be "
                "rate-limiting or down right now. Try again in a bit."
            )
    finally:
        # Abandon a hung worker instead of joining it; it shares no state.
        pool.shutdown(wait=False, cancel_futures=True)

    log.info("web_search_done", engine="ddgs", query=query[:80], results=len(hits))
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
