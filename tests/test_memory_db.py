"""Tests for the low-level SQLite memory database.

Uses a temporary directory so we never touch the user's real ``~/.yumii``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio

from yumii.core import memory_db

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Redirect the memory DB to a temporary file for the test."""
    test_db = tmp_path / "test_memory.db"
    monkeypatch.setattr(memory_db, "MEMORY_DIR", tmp_path)
    monkeypatch.setattr(memory_db, "DB_PATH", test_db)
    await memory_db.init_db()
    return test_db


@pytest.mark.asyncio
async def test_init_db_creates_tables(isolated_db: Path) -> None:
    """init_db() should create all required tables without error."""
    # If init_db() in the fixture succeeds, tables exist.
    # Let's verify by running a simple query against each table.
    rows_sessions = await memory_db.fetchall("SELECT name FROM sqlite_master WHERE type='table'")
    table_names = {r["name"] for r in rows_sessions}
    assert "sessions" in table_names
    assert "session_summaries" in table_names


@pytest.mark.asyncio
async def test_execute_and_fetchone(isolated_db: Path) -> None:
    """execute() and fetchone() should round-trip a write/read."""
    await memory_db.execute(
        "INSERT INTO sessions (id, name) VALUES (?, ?)",
        ("sess-1", "Test Session"),
    )
    row = await memory_db.fetchone("SELECT * FROM sessions WHERE id = ?", ("sess-1",))
    assert row is not None
    assert row["name"] == "Test Session"


@pytest.mark.asyncio
async def test_fetchall_returns_list(isolated_db: Path) -> None:
    """fetchall() should return a list of Row objects."""
    for i in range(3):
        await memory_db.execute(
            "INSERT INTO sessions (id, name) VALUES (?, ?)",
            (f"sess-{i}", f"Session {i}"),
        )
    rows = await memory_db.fetchall("SELECT * FROM sessions ORDER BY id")
    assert len(rows) == 3
    assert rows[0]["id"] == "sess-0"


@pytest.mark.asyncio
async def test_transaction_context_manager(isolated_db: Path) -> None:
    """transaction() should yield a connection that supports commit."""
    async with memory_db.transaction() as db:
        await db.execute(
            "INSERT INTO sessions (id, name) VALUES (?, ?)",
            ("sess-transaction", "Transaction Test"),
        )
        await db.commit()

    rows = await memory_db.fetchall("SELECT * FROM sessions WHERE id = ?", ("sess-transaction",))
    assert len(rows) == 1
    assert rows[0]["name"] == "Transaction Test"
