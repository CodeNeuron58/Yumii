"""Session management for Yumii.

Each browser conversation is a **session** identified by a UUID.  Sessions are
stored in SQLite and survive server restarts.  The LangGraph checkpoint
saver (AsyncSqliteSaver) stores per-session conversation history in a
separate database file; this module only stores the session *metadata*.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from yumii.core.memory_db import execute, fetchall, fetchone
from yumii.core.logging import get_logger

log = get_logger(__name__)

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
        await execute(
            "INSERT INTO sessions (id, name) VALUES (?, ?)",
            (session_id, name),
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
                "UPDATE sessions SET last_active_at = CURRENT_TIMESTAMP,"
                " message_count = ? WHERE id = ?",
                (message_count, session_id),
            )
        else:
            await execute(
                "UPDATE sessions SET last_active_at = CURRENT_TIMESTAMP"
                " WHERE id = ?",
                (session_id,),
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
