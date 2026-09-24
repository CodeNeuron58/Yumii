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


# ── Session continuity across restarts ─────────────────────────────────


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    from yumii.core import global_config as gc

    monkeypatch.setattr(gc, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(gc, "CONFIG_FILE", tmp_path / "config.json")
    return gc


@pytest.mark.asyncio
async def test_restore_last_session_resumes_it(isolated_config, monkeypatch):
    from yumii.core import engine as engine_module

    isolated_config.update_global_config("LAST_SESSION_ID", "s-9")

    e = YumiiEngine()
    assert e.active_session_id is None

    class _Session:
        id = "s-9"
        name = "Robotics chat"

    async def fake_get(session_id):
        return _Session() if session_id == "s-9" else None

    monkeypatch.setattr(engine_module.session_manager, "get_session", fake_get)
    rebuilt: list[bool] = []

    async def fake_ctx(include_current):
        rebuilt.append(include_current)

    e._rebuild_session_context = fake_ctx

    await e._restore_last_session()

    assert e.active_session_id == "s-9"
    assert e.active_session_name == "Robotics chat"
    assert rebuilt == [True]


@pytest.mark.asyncio
async def test_restore_skips_when_session_is_gone(isolated_config, monkeypatch):
    from yumii.core import engine as engine_module

    isolated_config.update_global_config("LAST_SESSION_ID", "deleted-id")
    e = YumiiEngine()

    async def fake_get(session_id):
        return None

    monkeypatch.setattr(engine_module.session_manager, "get_session", fake_get)

    await e._restore_last_session()
    assert e.active_session_id is None  # fresh start, no stale reference


@pytest.mark.asyncio
async def test_restore_never_overrides_a_live_session(isolated_config, monkeypatch):
    e = YumiiEngine()
    e.active_session_id = "already-active"

    async def fail(*args, **kwargs):
        raise AssertionError("get_session must not be called")

    monkeypatch.setattr(engine_module.session_manager, "get_session", fail)

    await e._restore_last_session()
    assert e.active_session_id == "already-active"


@pytest.mark.asyncio
async def test_create_new_session_persists_last_session(isolated_config, monkeypatch):
    from yumii.core import engine as engine_module

    e = YumiiEngine()

    async def fake_create(name):
        return "s-new-1"

    async def fake_facts():
        return []

    async def fake_ctx(include_current):
        return None

    monkeypatch.setattr(engine_module.session_manager, "create_session", fake_create)
    monkeypatch.setattr(engine_module.memory_manager, "get_facts_raw", fake_facts)
    e._rebuild_session_context = fake_ctx

    await e.create_new_session(name="Fresh")

    assert e.active_session_id == "s-new-1"
    assert isolated_config.load_global_config()["LAST_SESSION_ID"] == "s-new-1"
