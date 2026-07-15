"""Session summaries + time sense — Yumii's episodic memory.

Writes the ``session_summaries`` table (schema in memory_db) from the
searchable transcript, and builds the "shared history" block the
engine injects into the system prompt at session start:

    You last spoke with them 2 days ago.
    Recent conversations:
    - 2 days ago, "Kyoto trip": user booked Kyoto for October 12th …
    Earlier in this conversation: …

Summaries are produced by the same cheap LLM the memory review uses,
watermarked by transcript message count so an unchanged session is
never re-summarized. Facts answer "what is true about the user";
summaries answer "what happened between us, and when".
"""

from __future__ import annotations

from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage

from yumii.core.logging import get_logger
from yumii.core.memory_db import execute, fetchall, fetchone

log = get_logger(__name__)

# Re-summarize a live session every this many transcript messages
# (20 messages = 10 spoken turns), so a long conversation's summary
# stays current and carries what slid out of the history window.
SUMMARY_REFRESH_MESSAGES = 20

# Bounds on what the summarizer LLM sees / returns.
_MAX_ROWS = 80          # most recent transcript rows fed to the LLM
_MAX_ROW_CHARS = 400    # per-message cap
_MAX_SUMMARY_CHARS = 600

_SUMMARY_SYSTEM_PROMPT = """\
You summarize one conversation between a user and Yumii, their AI \
companion, so Yumii can remember it later. Write 2-4 plain sentences, \
past tense, third person ("the user...", "Yumii..."). Capture: what \
the user shared or asked about, decisions made, the emotional tone if \
notable, and any open threads or promises (things to follow up on). \
Skip pleasantries and filler. Output ONLY the summary text — no \
headings, no quotes, no preamble."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")


# ---------------------------------------------------------------------------
# Time sense
# ---------------------------------------------------------------------------


def humanize_ago(ts: str | None) -> str:
    """'2026-07-13 09:15:00(.123)' → 'two days ago'-style phrasing.

    Voice-first: returns words the TTS can speak naturally, never raw
    timestamps. Unparseable input degrades to 'a while ago'.
    """
    if not ts:
        return "a while ago"
    parsed = None
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            parsed = datetime.strptime(ts.strip(), fmt).replace(tzinfo=timezone.utc)
            break
        except ValueError:
            continue
    if parsed is None:
        return "a while ago"

    seconds = (datetime.now(timezone.utc) - parsed).total_seconds()
    if seconds < 120:
        return "just now"
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes} minutes ago"
    hours = int(seconds // 3600)
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = int(seconds // 86400)
    if days < 2:
        return "yesterday"
    if days < 14:
        return f"{days} days ago"
    weeks = days // 7
    return f"{weeks} week{'s' if weeks != 1 else ''} ago"


# ---------------------------------------------------------------------------
# Summarization
# ---------------------------------------------------------------------------


async def summarize_session(session_id: str) -> str | None:
    """Summarize a session's transcript into ``session_summaries``.

    Watermarked: if the stored summary already covers the current
    transcript length, this is a no-op. Returns the summary text, or
    None when there was nothing (new) to summarize or the LLM failed —
    a failed summary must never disturb anything.
    """
    if not session_id:
        return None

    rows = await fetchall(
        "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id",
        (session_id,),
    )
    if len(rows) < 2:
        return None

    existing = await fetchone(
        "SELECT message_count FROM session_summaries WHERE session_id = ?",
        (session_id,),
    )
    if existing and existing["message_count"] >= len(rows):
        return None  # nothing new since the last summary

    lines = [
        f"[{'User' if r['role'] == 'user' else 'Yumii'}]: {r['content'][:_MAX_ROW_CHARS]}"
        for r in rows[-_MAX_ROWS:]
    ]

    from yumii.agent.fact_extractor import _get_extractor_llm

    try:
        llm = _get_extractor_llm()
        response = await llm.ainvoke(
            [
                SystemMessage(content=_SUMMARY_SYSTEM_PROMPT),
                HumanMessage(content="\n".join(lines)),
            ]
        )
    except Exception as exc:
        log.warning("session_summary_llm_failed", session_id=session_id, error=str(exc))
        return None

    summary = str(getattr(response, "content", "") or "").strip()[:_MAX_SUMMARY_CHARS]
    if not summary:
        return None

    await execute(
        "INSERT INTO session_summaries (session_id, summary, message_count, updated_at)"
        " VALUES (?, ?, ?, ?)"
        " ON CONFLICT(session_id) DO UPDATE SET"
        " summary = excluded.summary,"
        " message_count = excluded.message_count,"
        " updated_at = excluded.updated_at",
        (session_id, summary, len(rows), _utc_now()),
    )
    log.info("session_summarized", session_id=session_id, messages=len(rows))
    return summary


# ---------------------------------------------------------------------------
# The prompt block
# ---------------------------------------------------------------------------


async def build_session_context(
    current_session_id: str,
    *,
    include_current: bool = False,
    max_recent: int = 3,
) -> str:
    """Assemble the shared-history block for the system prompt.

    ``include_current`` adds this session's own summary ("Earlier in
    this conversation…") — used on resume and for long live sessions
    whose early turns have slid out of the history window.
    """
    parts: list[str] = []

    last = await fetchone(
        "SELECT last_active_at FROM sessions"
        " WHERE id != ? AND is_archived = 0"
        " ORDER BY last_active_at DESC LIMIT 1",
        (current_session_id,),
    )
    if last is None:
        return "This is your very first conversation with them."
    parts.append(f"You last spoke with them {humanize_ago(last['last_active_at'])}.")

    recents = await fetchall(
        "SELECT ss.summary, s.name, s.last_active_at"
        " FROM session_summaries ss JOIN sessions s ON s.id = ss.session_id"
        " WHERE ss.session_id != ? AND s.is_archived = 0"
        " ORDER BY s.last_active_at DESC LIMIT ?",
        (current_session_id, max_recent),
    )
    if recents:
        parts.append("Recent conversations:")
        for r in recents:
            parts.append(
                f"- {humanize_ago(r['last_active_at'])}, "
                f"\"{r['name']}\": {r['summary']}"
            )

    if include_current:
        own = await fetchone(
            "SELECT summary FROM session_summaries WHERE session_id = ?",
            (current_session_id,),
        )
        if own and own["summary"]:
            parts.append(f"Earlier in this conversation: {own['summary']}")

    return "\n".join(parts)
