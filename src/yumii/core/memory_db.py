"""SQLite layer for Yumii's local memory at ~/.yumii/memory/yumii.db."""

from __future__ import annotations

from pathlib import Path
from typing import Any, AsyncGenerator

import aiosqlite
from contextlib import asynccontextmanager

MEMORY_DIR = Path.home() / ".yumii" / "memory"
DB_PATH = MEMORY_DIR / "yumii.db"

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
# messages is the searchable transcript; messages_fts is an FTS5
# (external-content, porter-stemmed) index over it, kept in sync by triggers.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    name TEXT DEFAULT 'New Chat',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    message_count INTEGER DEFAULT 0,
    is_archived INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS session_summaries (
    session_id TEXT PRIMARY KEY,
    summary TEXT,
    message_count INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id);

CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    content,
    content='messages',
    content_rowid='id',
    tokenize='porter unicode61'
);

CREATE TRIGGER IF NOT EXISTS messages_after_insert AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
END;
CREATE TRIGGER IF NOT EXISTS messages_after_delete AFTER DELETE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, content)
    VALUES ('delete', old.id, old.content);
END;
"""

# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------


async def _get_connection() -> aiosqlite.Connection:
    """Open a new async SQLite connection with row factory enabled."""
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON")
    return db


async def init_db() -> None:
    """Create tables if they do not already exist."""
    db = await _get_connection()
    try:
        await db.executescript(_SCHEMA)
        await db.commit()
    finally:
        await db.close()


async def execute(
    sql: str,
    parameters: tuple[Any, ...] | list[Any] | None = None,
) -> aiosqlite.Cursor:
    """Execute one statement, commit, and return the cursor (prefer transaction())."""
    db = await _get_connection()
    try:
        cursor = await db.execute(sql, parameters or ())
        await db.commit()
        return cursor
    finally:
        await db.close()


async def fetchone(
    sql: str,
    parameters: tuple[Any, ...] | list[Any] | None = None,
) -> aiosqlite.Row | None:
    """Run a SELECT and return the first row, or ``None``."""
    db = await _get_connection()
    try:
        cursor = await db.execute(sql, parameters or ())
        row = await cursor.fetchone()
        return row
    finally:
        await db.close()


async def fetchall(
    sql: str,
    parameters: tuple[Any, ...] | list[Any] | None = None,
) -> list[aiosqlite.Row]:
    """Run a SELECT and return every row."""
    db = await _get_connection()
    try:
        cursor = await db.execute(sql, parameters or ())
        rows = await cursor.fetchall()
        return rows
    finally:
        await db.close()


@asynccontextmanager
async def transaction() -> AsyncGenerator[aiosqlite.Connection, None]:
    """Async context manager yielding a connection with an open transaction."""
    db = await _get_connection()
    try:
        yield db
    finally:
        await db.close()
