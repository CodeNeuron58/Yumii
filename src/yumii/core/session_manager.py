"""Session management for Yumii.

Each browser conversation is a **session** identified by a UUID.  Sessions are
stored in SQLite and survive server restarts.  The LangGraph checkpoint
saver (AsyncSqliteSaver) stores per-session conversation history in a
separate database file; this module only stores the session *metadata*.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from yumii.core.memory_db import execute, fetchall, fetchone
from yumii.core.logging import get_logger

log = get_logger(__name__)


def _utc_now() -> str:
    """UTC timestamp with microsecond precision.

    SQLite's CURRENT_TIMESTAMP only has 1-second resolution, so sessions
    created/touched within the same second got identical ``last_active_at``
    values and ``ORDER BY last_active_at`` became nondeterministic (flaky
    ordering test on fast CI machines). Same format prefix as the old
    values ("YYYY-MM-DD HH:MM:SS"), so old and new rows still sort
    correctly against each other as strings.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SessionRow:
    """A single session record as returned from the database."""

    id: str
    name: str
    created_at: str
    last_active_at: str
    message_count: int
    is_archived: bool

    @classmethod
    def from_row(cls, row: Any) -> "SessionRow":
        return cls(
            id=row["id"],
            name=row["name"],
            created_at=row["created_at"],
            last_active_at=row["last_active_at"],
            message_count=row["message_count"],
            is_archived=bool(row["is_archived"]),
        )


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


class SessionManager:
    """Async CRUD for Yumii conversation sessions."""

    async def create_session(self, name: str | None = None) -> str:
        """Create a new session and return its UUID."""
        session_id = str(uuid.uuid4())
        name = name or "New Chat"
        now = _utc_now()
        await execute(
            "INSERT INTO sessions (id, name, created_at, last_active_at)"
            " VALUES (?, ?, ?, ?)",
            (session_id, name, now, now),
        )
        log.info("session_created", session_id=session_id, name=name)
        return session_id

    async def list_sessions(
        self,
        *,
        include_archived: bool = False,
        limit: int = 50,
    ) -> list[SessionRow]:
        """Return sessions ordered by most recently active first."""
        if include_archived:
            sql = (
                "SELECT * FROM sessions ORDER BY last_active_at DESC, created_at DESC LIMIT ?"
            )
            params: tuple[Any, ...] = (limit,)
        else:
            sql = (
                "SELECT * FROM sessions WHERE is_archived = 0"
                " ORDER BY last_active_at DESC, created_at DESC LIMIT ?"
            )
            params = (limit,)

        rows = await fetchall(sql, params)
        return [SessionRow.from_row(r) for r in rows]

    async def get_session(self, session_id: str) -> SessionRow | None:
        """Fetch a single session by ID."""
        row = await fetchone(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        )
        if row is None:
            return None
        return SessionRow.from_row(row)

    async def update_session_activity(
        self,
        session_id: str,
        *,
        message_count: int | None = None,
    ) -> None:
        """Touch ``last_active_at`` and optionally bump ``message_count``."""
        if message_count is not None:
            await execute(
                "UPDATE sessions SET last_active_at = ?,"
                " message_count = ? WHERE id = ?",
                (_utc_now(), message_count, session_id),
            )
        else:
            await execute(
                "UPDATE sessions SET last_active_at = ?"
                " WHERE id = ?",
                (_utc_now(), session_id),
            )

    async def bump_after_turn(self, session_id: str, user_text: str) -> None:
        """Book-keeping after a completed conversation turn.

        Bumps ``message_count`` by 2 (user + assistant), touches
        ``last_active_at``, and — if the session still has the default
        name — titles it from the user's first utterance so the history
        UI shows something recognisable instead of a wall of "New Chat".
        """
        session = await self.get_session(session_id)
        if session is None:
            return
        if session.name == "New Chat":
            title = re.sub(r"\s+", " ", user_text).strip()[:48]
            if title:
                await self.rename_session(session_id, title)
        await execute(
            "UPDATE sessions SET message_count = message_count + 2,"
            " last_active_at = ? WHERE id = ?",
            (_utc_now(), session_id),
        )

    async def rename_session(self, session_id: str, name: str) -> None:
        """Change the human-readable name of a session."""
        await execute(
            "UPDATE sessions SET name = ? WHERE id = ?", (name, session_id)
        )
        log.info("session_renamed", session_id=session_id, name=name)

    async def archive_session(self, session_id: str) -> None:
        """Soft-delete a session (hide from default lists)."""
        await execute(
            "UPDATE sessions SET is_archived = 1 WHERE id = ?",
            (session_id,),
        )
        log.info("session_archived", session_id=session_id)

    async def delete_session(self, session_id: str) -> None:
        """Hard-delete a session and its summary."""
        await execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        await execute(
            "DELETE FROM session_summaries WHERE session_id = ?",
            (session_id,),
        )
        log.info("session_deleted", session_id=session_id)

    async def get_last_active_session(self) -> SessionRow | None:
        """Return the most recently active non-archived session, if any."""
        rows = await self.list_sessions(limit=1)
        return rows[0] if rows else None


# Global singleton — safe because all methods are async and stateless.
session_manager = SessionManager()
