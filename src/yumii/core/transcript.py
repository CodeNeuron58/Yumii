"""Searchable conversation transcript (FTS5) — the cross-session recall layer."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from yumii.core.logging import get_logger
from yumii.core.memory_db import execute, fetchall, fetchone, transaction

log = get_logger(__name__)

# FTS rows to scan before deduping by session, distinct sessions to return,
# and messages shown around a hit (each side).
_SCAN_LIMIT = 60
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
    tokens = re.findall(r"[A-Za-z0-9_]+", raw)
    return " ".join(f'"{t}"' for t in tokens)


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


async def search(query: str, max_sessions: int = _MAX_SESSIONS) -> list[TranscriptHit]:
    """Full-text search across all conversations, best hit per session (BM25; AND then OR)."""
    match = _fts_query(query)
    if not match:
        return []

    sql = (
        "SELECT m.id, m.session_id, m.role, m.created_at,"
        "       COALESCE(s.name, '(deleted session)') AS session_name,"
        "       snippet(messages_fts, 0, '»', '«', ' … ', 16) AS snip,"
        "       bm25(messages_fts) AS rank"
        " FROM messages_fts"
        " JOIN messages m ON m.id = messages_fts.rowid"
        " LEFT JOIN sessions s ON s.id = m.session_id"
        " WHERE messages_fts MATCH ?"
        " ORDER BY rank LIMIT ?"
    )
    rows = await fetchall(sql, (match, _SCAN_LIMIT))
    if not rows and " " in match:
        rows = await fetchall(sql, (match.replace(" ", " OR "), _SCAN_LIMIT))

    # Keep the best-ranked hit per session (rows arrive ranked).
    hits: list[TranscriptHit] = []
    seen_sessions: set[str] = set()
    for r in rows:
        sid = r["session_id"]
        if sid in seen_sessions:
            continue
        seen_sessions.add(sid)
        hits.append(
            TranscriptHit(
                message_id=r["id"],
                session_id=sid,
                session_name=r["session_name"],
                role=r["role"],
                snippet=r["snip"],
                created_at=r["created_at"] or "",
                window=await _window(sid, r["id"]),
            )
        )
        if len(hits) >= max_sessions:
            break
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
