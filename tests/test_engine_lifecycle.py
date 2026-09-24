"""Engine lifecycle: shutdown must stop background work before closing stores.

Regression for the audit finding that shutdown() closed the checkpoint
connection and the memory store while loop tasks and fire-and-forget tasks
were still running — a turn in flight wrote checkpoints into a closed
connection, and pending memory reviews died with their turns already drained.
"""

import asyncio

import pytest

from yumii.core import engine as engine_module
from yumii.core.engine import YumiiEngine


@pytest.fixture
def quiet_memory(monkeypatch):
    """Stub the memory manager's DB-backed calls (real one touches disk)."""

    async def fake_review(turns, session_id):
        return None

    async def fake_close():
        return None

    monkeypatch.setattr(engine_module.memory_manager, "review_recent_turns", fake_review)
    monkeypatch.setattr(engine_module.memory_manager, "close", fake_close)


@pytest.mark.asyncio
async def test_shutdown_cancels_background_tasks_before_closing_stores(
    quiet_memory, monkeypatch
):
    e = YumiiEngine()
    order: list[str] = []
    started = asyncio.Event()

    async def fake_loop():
        started.set()
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            order.append("task-cancelled")
            raise

    e._spawn(fake_loop())
    e._spawn(fake_loop())

    class _Conn:
        async def close(self):
            order.append("conn-closed")

    e._conn = _Conn()

    # record the memory-store close too (the fixture's stub is silent)
    async def fake_memory_close():
        order.append("memory-closed")

    monkeypatch.setattr(engine_module.memory_manager, "close", fake_memory_close)

    await asyncio.wait_for(started.wait(), timeout=2.0)
    await asyncio.wait_for(e.shutdown(), timeout=15.0)

    # both tasks were cancelled BEFORE either store was closed
    assert sorted(order[:2]) == ["task-cancelled", "task-cancelled"]
    assert order[2:] == ["conn-closed", "memory-closed"]
    assert e._background_tasks == set()  # done-callbacks cleaned up


@pytest.mark.asyncio
async def test_shutdown_reviews_buffered_turns_per_session(quiet_memory, monkeypatch):
    """Buffered turns are grouped by their owning session — a stale active id
    must not capture another session's turns on the way out."""
    e = YumiiEngine()
    calls: list[tuple[str, list[dict]]] = []

    async def fake_review(turns, session_id):
        calls.append((session_id, list(turns)))

    monkeypatch.setattr(engine_module.memory_manager, "review_recent_turns", fake_review)

    e._memory_turn_buffer = [
        ("s1", {"role": "user", "content": "a"}),
        ("s2", {"role": "user", "content": "b"}),
        ("s1", {"role": "assistant", "content": "c"}),
    ]
    e.active_session_id = "s2"
    await asyncio.wait_for(e.shutdown(), timeout=15.0)

    by_session = {sid: turns for sid, turns in calls}
    assert [t["content"] for t in by_session["s1"]] == ["a", "c"]
    assert [t["content"] for t in by_session["s2"]] == ["b"]
    assert e._memory_turn_buffer == []


@pytest.mark.asyncio
async def test_shutdown_is_idle_safe(quiet_memory):
    """Shutting down with nothing running and no connection must not raise."""
    e = YumiiEngine()
    await asyncio.wait_for(e.shutdown(), timeout=15.0)
