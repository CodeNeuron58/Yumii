"""Past-conversation recall tool — full-text search over the transcript.

Registered with a READ policy (no confirmation gate): it only reads the
user's own local transcript, and gating recall behind a permission
popup would make "what did we talk about last week?" feel broken.

One tool, three shapes (inferred from the arguments, Hermes-style):

* ``query``                         → search all past conversations (FTS5/BM25)
* ``session_id`` + ``message_id``   → read more context around one hit
* no arguments                      → list recent conversations

Every result is stored text straight from SQLite — no LLM calls.
"""

from __future__ import annotations

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from yumii.core.logging import get_logger
from yumii.tools.policy import ToolCategory, ToolPolicy
from yumii.tools.registry import register

log = get_logger(__name__)


class RecallInput(BaseModel):
    """Input schema for :func:`search_past_conversations`."""

    query: str | None = Field(
        default=None,
        description=(
            "Words to search for across all past conversations, e.g. "
            "'birthday plans' or 'that python bug'. Plain words work best; "
            "word forms match automatically (run/running)."
        ),
    )
    session_id: str | None = Field(
        default=None,
        description=(
            "To read more of one conversation: the session_id from an "
            "earlier search result. Use together with message_id."
        ),
    )
    message_id: int | None = Field(
        default=None,
        description=(
            "The message id from an earlier search result to read the "
            "surrounding conversation of. Use together with session_id."
        ),
    )


def _fmt_ts(ts: str) -> str:
    """Trim '2026-07-15 00:31:22.123456' to '2026-07-15 00:31'."""
    return ts[:16] if ts else "unknown time"


def _fmt_window(window: list[dict]) -> str:
    lines = []
    for m in window:
        who = "User" if m["role"] == "user" else "Yumii"
        text = m["content"]
        if len(text) > 300:
            text = text[:300] + "…"
        lines.append(f"  [{m['id']}] {who}: {text}")
    return "\n".join(lines)


@tool("search_past_conversations", args_schema=RecallInput)
async def search_past_conversations(
    query: str | None = None,
    session_id: str | None = None,
    message_id: int | None = None,
) -> str:
    """Recall past conversations with the user — your long-term episodic memory.

    Use when the user refers to something discussed before ("that thing we
    talked about", "what did I say about X", "last week you told me…") or
    when older context would clearly help. Three ways to call it:
    query="words" searches everything you've ever discussed; session_id +
    message_id (from a previous result) reads the surrounding conversation;
    no arguments lists recent conversations. Results are the real stored
    messages with timestamps.
    """
    from yumii.core import transcript

    # Scroll: read around one message.
    if session_id and message_id is not None:
        window = await transcript.window_around(session_id, int(message_id))
        if not window:
            return "No messages found there — the conversation may have been deleted."
        return (
            f"Conversation context around message {message_id}:\n"
            + _fmt_window(window)
        )

    # Discover: full-text search.
    if query and query.strip():
        hits = await transcript.search(query.strip())
        if not hits:
            return (
                f"No past conversation mentions '{query.strip()}'. "
                "It may have been phrased differently — try other words."
            )
        parts = [f"Found {len(hits)} past conversation(s) mentioning it:"]
        for h in hits:
            parts.append(
                f"\n— Conversation '{h.session_name}' (session_id={h.session_id}), "
                f"around {_fmt_ts(h.created_at)}, match: {h.snippet}\n"
                + _fmt_window(h.window)
            )
        parts.append(
            "\n(To read more around a hit, call again with session_id and "
            "the [message id].)"
        )
        return "\n".join(parts)

    # Browse: recent conversations.
    sessions = await transcript.recent_sessions()
    if not sessions:
        return "No past conversations recorded yet."
    lines = ["Recent conversations:"]
    for s in sessions:
        lines.append(
            f"— '{s['name']}' (session_id={s['session_id']}), "
            f"last active {_fmt_ts(s['last_active'])}: opened with "
            f"\"{s['opened_with']}\""
        )
    return "\n".join(lines)


# Pure read of the user's own local history — no confirmation gate, so
# recall feels instant instead of interrogative.
register(
    search_past_conversations,
    ToolPolicy(
        category=ToolCategory.READ,
        requires_confirmation=False,
    ),
)


__all__ = ["RecallInput", "search_past_conversations"]
