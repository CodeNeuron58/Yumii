"""Tests for the session manager.

Uses a temporary directory so we never touch the user's real ``~/.yumii``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio

from yumii.core import memory_db
from yumii.core.session_manager import SessionManager

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def isolated_sessions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Redirect the memory DB to a temporary file for the test."""
    monkeypatch.setattr(memory_db, "MEMORY_DIR", tmp_path)
    monkeypatch.setattr(memory_db, "DB_PATH", tmp_path / "test.db")
    await memory_db.init_db()
    sm = SessionManager()
    return sm


@pytest.mark.asyncio
async def test_create_session_returns_uuid(isolated_sessions: SessionManager) -> None:
    """create_session() should return a valid-looking UUID string."""
    sid = await isolated_sessions.create_session("My Chat")
    assert isinstance(sid, str)
    assert len(sid) == 36  # UUID v4 length
    assert "-" in sid


@pytest.mark.asyncio
async def test_list_sessions_ordered_by_activity(isolated_sessions: SessionManager) -> None:
    """list_sessions() should return sessions newest-first."""
    sid1 = await isolated_sessions.create_session("First")
    sid2 = await isolated_sessions.create_session("Second")
    # Explicitly touch the first session so it becomes the most recent.
    await isolated_sessions.update_session_activity(sid1)
    sessions = await isolated_sessions.list_sessions()
    assert len(sessions) == 2
    assert sessions[0].id == sid1
    assert sessions[1].id == sid2


@pytest.mark.asyncio
async def test_get_session_found(isolated_sessions: SessionManager) -> None:
    """get_session() should return the row for an existing session."""
    sid = await isolated_sessions.create_session("Find Me")
    row = await isolated_sessions.get_session(sid)
    assert row is not None
    assert row.name == "Find Me"
    assert row.is_archived is False


@pytest.mark.asyncio
async def test_get_session_missing(isolated_sessions: SessionManager) -> None:
    """get_session() should return None for a non-existent ID."""
    row = await isolated_sessions.get_session("does-not-exist")
    assert row is None


@pytest.mark.asyncio
async def test_rename_session(isolated_sessions: SessionManager) -> None:
    """rename_session() should update the name field."""
    sid = await isolated_sessions.create_session("Old Name")
    await isolated_sessions.rename_session(sid, "New Name")
    row = await isolated_sessions.get_session(sid)
    assert row is not None
    assert row.name == "New Name"


@pytest.mark.asyncio
async def test_archive_and_list(isolated_sessions: SessionManager) -> None:
    """Archived sessions should not appear in the default list."""
    sid = await isolated_sessions.create_session("Archive Me")
    await isolated_sessions.archive_session(sid)
    default = await isolated_sessions.list_sessions()
    assert all(s.id != sid for s in default)
    archived = await isolated_sessions.list_sessions(include_archived=True)
    assert any(s.id == sid for s in archived)


@pytest.mark.asyncio
async def test_delete_session_removes_row(isolated_sessions: SessionManager) -> None:
    """delete_session() should permanently remove the session."""
    sid = await isolated_sessions.create_session("Delete Me")
    await isolated_sessions.delete_session(sid)
    assert await isolated_sessions.get_session(sid) is None


@pytest.mark.asyncio
async def test_last_active_session(isolated_sessions: SessionManager) -> None:
    """get_last_active_session() should return the most recently touched session."""
    sid1 = await isolated_sessions.create_session("A")
    await isolated_sessions.create_session("B")
    await isolated_sessions.update_session_activity(sid1)
    last = await isolated_sessions.get_last_active_session()
    assert last is not None
    assert last.id == sid1
