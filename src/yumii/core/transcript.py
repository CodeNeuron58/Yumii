"""Searchable conversation transcript (FTS5) — the cross-session recall layer."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from yumii.core.logging import get_logger
from yumii.core.memory_db import execute, fetchall, fetchone, transaction

log = get_logger(__name__)

# Distinct sessions to return, and messages shown around a hit (each side).
_MAX_SESSIONS = 3
_WINDOW = 3


def _utc_now() -> str:
    """Same timestamp format as session_manager (sorts as text)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")


@dataclass(frozen=True)
class TranscriptHit:
    """One matched message plus its surroundings."""

    message_id: int
    session_id: str
    session_name: str
    role: str
    snippet: str
    created_at: str
    window: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# Write path
# ---------------------------------------------------------------------------


async def record_turn(session_id: str, user_text: str, assistant_text: str) -> None:
    """Append one completed turn (user + assistant) to the transcript."""
    now = _utc_now()
    async with transaction() as db:
        await db.execute(
            "INSERT INTO messages (session_id, role, content, created_at)"
            " VALUES (?, ?, ?, ?)",
            (session_id, "user", user_text, now),
        )
        await db.execute(
            "INSERT INTO messages (session_id, role, content, created_at)"
            " VALUES (?, ?, ?, ?)",
            (session_id, "assistant", assistant_text, now),
        )
        await db.commit()


async def record_many(
    session_id: str, turns: list[tuple[str, str]], created_at: str | None = None
) -> int:
    """Bulk-append ``(role, content)`` rows — used by the checkpoint backfill."""
    if not turns:
        return 0
    ts = created_at or _utc_now()
    async with transaction() as db:
        await db.executemany(
            "INSERT INTO messages (session_id, role, content, created_at)"
            " VALUES (?, ?, ?, ?)",
            [(session_id, role, content, ts) for role, content in turns],
        )
        await db.commit()
    return len(turns)


async def delete_session_messages(session_id: str) -> None:
    """Remove a deleted session's transcript (FTS rows go via trigger)."""
    await execute("DELETE FROM messages WHERE session_id = ?", (session_id,))


async def is_empty() -> bool:
    """True when no transcript has ever been recorded (backfill gate)."""
    row = await fetchone("SELECT 1 FROM messages LIMIT 1")
    return row is None


# ---------------------------------------------------------------------------
# Read path
# ---------------------------------------------------------------------------


def _fts_query(raw: str) -> str:
    """Turn free text into a safe FTS5 MATCH expression (each token quoted; AND semantics)."""
    # \w with UNICODE: the index uses the unicode61 tokenizer, so accented
    # and non-Latin queries must not be filtered to ASCII.
    tokens = re.findall(r"\w+", raw, re.UNICODE)
    return " ".join(f'"{t}"' for t in tokens)


def _build_snippet(content: str, query: str, width: int = 140) -> str:
    """A Python-side snippet around the first matching term (SQLite's snippet()
    is unavailable once the query leaves the plain MATCH context)."""
    lowered = (content or "").lower()
    pos = -1
    for token in re.findall(r"\w+", query, re.UNICODE):
        pos = lowered.find(token.lower())
        if pos != -1:
            break
    if pos == -1:
        return (content or "")[:width]
    start = max(0, pos - 40)
    end = min(len(content), start + width)
    prefix = "…" if start else ""
    suffix = "…" if end < len(content) else ""
    return f"{prefix}{content[start:end]}{suffix}"


async def _window(session_id: str, anchor_id: int, span: int = _WINDOW) -> list[dict[str, Any]]:
    """Messages around ``anchor_id`` within one session, oldest first."""
    before = await fetchall(
        "SELECT id, role, content, created_at FROM messages"
        " WHERE session_id = ? AND id < ? ORDER BY id DESC LIMIT ?",
        (session_id, anchor_id, span),
    )
    at_and_after = await fetchall(
        "SELECT id, role, content, created_at FROM messages"
        " WHERE session_id = ? AND id >= ? ORDER BY id ASC LIMIT ?",
        (session_id, anchor_id, span + 1),
    )
    rows = list(reversed(before)) + list(at_and_after)
    return [dict(r) for r in rows]


async def search(
    query: str,
    max_sessions: int = _MAX_SESSIONS,
    since_days: int | None = None,
) -> list[TranscriptHit]:
    """Full-text search across all conversations, best hit per session (BM25; AND then OR).

    ``since_days`` bounds the search to recent conversations (1 = today).
    """
    match = _fts_query(query)
    if not match:
        return []

    where = "WHERE messages_fts MATCH ?"
    params: list[Any] = [match]
    if since_days is not None and since_days > 0:
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=int(since_days))
        ).strftime("%Y-%m-%d %H:%M:%S.%f")
        where += " AND m.created_at >= ?"
        params.append(cutoff)

    # Three steps, because SQLite forbids FTS auxiliary functions (bm25,
    # snippet) inside GROUP BY queries: (1) rank ALL matches in a plain MATCH
    # query, (2) dedupe by session in Python — per-session best BEFORE any
    # limiting, so one chatty session can't starve the others — (3) fetch the
    # chosen rows' details and build snippets from content.
    rank_sql = (
        "SELECT messages_fts.rowid AS mid, bm25(messages_fts) AS rank"
        " FROM messages_fts"
        " JOIN messages m ON m.id = messages_fts.rowid"
        f" {where} ORDER BY rank LIMIT 500"
    )
    ranked = await fetchall(rank_sql, tuple(params))
    if not ranked and " " in match:
        # AND semantics found nothing — fall back to OR before giving up.
        or_match = match.replace(" ", " OR ")
        ranked = await fetchall(rank_sql, (or_match, *params[1:]))

    best: dict[str, int] = {}
    # Session ids come with a second fetch — dedupe needs them here, so
    # fetch them for the ranked rows in one go.
    ids = [r["mid"] for r in ranked]
    if ids:
        id_rows = await fetchall(
            "SELECT id, session_id FROM messages WHERE id IN"
            f" ({','.join('?' * len(ids))})",
            ids,
        )
        session_of = {r["id"]: r["session_id"] for r in id_rows}
        for r in ranked:
            sid = session_of.get(r["mid"])
            if sid and sid not in best:
                best[sid] = r["mid"]
            if len(best) >= max_sessions:
                break
    if not best:
        return []

    chosen_ids = list(best.values())
    detail_sql = (
        "SELECT m.id, m.session_id, m.role, m.created_at, m.content,"
        "       COALESCE(s.name, '(deleted session)') AS session_name"
        " FROM messages m"
        " LEFT JOIN sessions s ON s.id = m.session_id"
        f" WHERE m.id IN ({','.join('?' * len(chosen_ids))})"
    )
    details = {r["id"]: r for r in await fetchall(detail_sql, chosen_ids)}

    hits: list[TranscriptHit] = []
    for sid, mid in best.items():
        r = details.get(mid)
        if r is None:
            continue
        hits.append(
            TranscriptHit(
                message_id=mid,
                session_id=sid,
                session_name=r["session_name"],
                role=r["role"],
                snippet=_build_snippet(r["content"], query),
                created_at=r["created_at"] or "",
                window=await _window(sid, mid),
            )
        )
    return hits


async def window_around(session_id: str, message_id: int, span: int = 5) -> list[dict[str, Any]]:
    """Scroll: a wider window around a specific message in a session."""
    return await _window(session_id, message_id, span)


async def recent_sessions(limit: int = 5) -> list[dict[str, Any]]:
    """Browse: latest conversations with first/last message previews."""
    sessions = await fetchall(
        "SELECT DISTINCT m.session_id,"
        "       COALESCE(s.name, '(deleted session)') AS name,"
        "       COALESCE(s.last_active_at, MAX(m.created_at)) AS last_active"
        " FROM messages m LEFT JOIN sessions s ON s.id = m.session_id"
        " GROUP BY m.session_id ORDER BY last_active DESC LIMIT ?",
        (limit,),
    )
    out: list[dict[str, Any]] = []
    for srow in sessions:
        sid = srow["session_id"]
        first = await fetchone(
            "SELECT content FROM messages WHERE session_id = ? AND role = 'user'"
            " ORDER BY id ASC LIMIT 1",
            (sid,),
        )
        out.append(
            {
                "session_id": sid,
                "name": srow["name"],
                "last_active": srow["last_active"],
                "opened_with": (first["content"][:120] if first else ""),
            }
        )
    return out
