"""Tests for the long-term memory (user facts) manager.

Uses a temporary directory so we never touch the user's real ``~/.yumii``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio

from yumii.core.memory_manager import MemoryManager

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def isolated_memory(tmp_path: Path):
    """Provide a MemoryManager backed by a temporary SQLite Store DB."""
    db_path = str(tmp_path / "store.db")
    mm = MemoryManager(db_path=db_path)
    yield mm
    await mm.close()


@pytest.mark.asyncio
async def test_store_and_get_fact(isolated_memory: MemoryManager) -> None:
    """store_fact() should persist and get_facts() should retrieve it."""
    fid = await isolated_memory.store_fact("user is vegetarian", category="preference")
    assert isinstance(fid, str)
    assert len(fid) > 0
    facts = await isolated_memory.get_facts()
    assert len(facts) == 1
    assert facts[0].fact == "user is vegetarian"
    assert facts[0].category == "preference"


@pytest.mark.asyncio
async def test_get_facts_formatted(isolated_memory: MemoryManager) -> None:
    """get_facts_formatted() should return a markdown-ish bullet list."""
    await isolated_memory.store_fact("likes jazz", category="preference")
    await isolated_memory.store_fact("lives in Tokyo", category="identity")
    formatted = await isolated_memory.get_facts_formatted()
    assert "likes jazz" in formatted
    assert "lives in Tokyo" in formatted
    assert "Things you know about the user:" in formatted


@pytest.mark.asyncio
async def test_get_facts_filtered_by_category(isolated_memory: MemoryManager) -> None:
    """get_facts() with categories should filter correctly."""
    await isolated_memory.store_fact("A", category="preference")
    await isolated_memory.store_fact("B", category="identity")
    prefs = await isolated_memory.get_facts(categories=["preference"])
    assert len(prefs) == 1
    assert prefs[0].fact == "A"


@pytest.mark.asyncio
async def test_delete_fact(isolated_memory: MemoryManager) -> None:
    """delete_fact() should remove a single fact."""
    fid = await isolated_memory.store_fact("to delete")
    await isolated_memory.delete_fact(fid)
    facts = await isolated_memory.get_facts()
    assert len(facts) == 0


@pytest.mark.asyncio
async def test_clear_all_facts(isolated_memory: MemoryManager) -> None:
    """clear_all_facts() should wipe the entire store."""
    for i in range(5):
        await isolated_memory.store_fact(f"fact {i}")
    await isolated_memory.clear_all_facts()
    assert len(await isolated_memory.get_facts()) == 0


@pytest.mark.asyncio
async def test_get_facts_raw(isolated_memory: MemoryManager) -> None:
    """get_facts_raw() should return plain strings without metadata."""
    await isolated_memory.store_fact("raw fact 1")
    await isolated_memory.store_fact("raw fact 2")
    raw = await isolated_memory.get_facts_raw()
    assert set(raw) == {"raw fact 1", "raw fact 2"}


@pytest.mark.asyncio
async def test_extract_facts_stub(isolated_memory: MemoryManager) -> None:
    """extract_facts_from_messages() is a stub and should return []."""
    result = await isolated_memory.extract_facts_from_messages([], "sess-1")
    assert result == []
