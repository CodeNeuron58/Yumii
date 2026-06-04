"""SQLite database layer for Yumii's persistent memory.

Manages the local SQLite database at ``~/.yumii/memory/yumii.db``.
All other memory modules (session_manager, memory_manager) build on top of
this low-level layer.
"""

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
"""

# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------


async def _get_connection() -> aiosqlite.Connection:
    """Open a new async SQLite connection with row factory enabled."""
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    # Enable foreign keys (good practice, even if we don't use FKs yet)
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
    """Execute a single statement and return the cursor.

    The caller is responsible for calling ``db.commit()`` and ``db.close()``
    if they hold onto the connection.  In most cases you should use
    :func:`transaction` instead.
    """
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
    """Async context manager that yields a connection with an open transaction.

    Usage::

        async with transaction() as db:
            await db.execute("INSERT ...")
            await db.execute("UPDATE ...")
            await db.commit()
    """
    db = await _get_connection()
    try:
        yield db
    finally:
        await db.close()
