"""Tests for agent-written memory: the manage_memory tool, the review
pass (delta operations), and the engine's review buffer.

Isolated stores throughout — never touches the user's real ~/.yumii.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
import pytest_asyncio

from yumii.agent.fact_extractor import _parse_review_json
from yumii.core.memory_manager import MemoryManager

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def isolated_memory(tmp_path: Path):
    db_path = str(tmp_path / "store.db")
    mm = MemoryManager(db_path=db_path)
    yield mm
    await mm.close()


@pytest_asyncio.fixture
async def tool_memory(isolated_memory, monkeypatch: pytest.MonkeyPatch):
    """Point the manage_memory tool's singleton at the isolated store."""
    from yumii.core import memory_manager as mm_module

    monkeypatch.setattr(mm_module, "memory_manager", isolated_memory)
    return isolated_memory


# ── Substring matching primitives ──────────────────────────────────────


async def test_replace_by_text_unique_match(isolated_memory: MemoryManager):
    await isolated_memory.store_fact("user's birthday is March 5th")
    result = await isolated_memory.replace_fact_by_text(
        "birthday", "user's birthday is March 3rd"
    )
    assert result == "replaced"
    facts = await isolated_memory.get_facts_raw()
    assert facts == ["user's birthday is March 3rd"]


async def test_replace_by_text_ambiguous(isolated_memory: MemoryManager):
    await isolated_memory.store_fact("likes coffee in the morning")
    await isolated_memory.store_fact("drinks coffee black")
    assert await isolated_memory.replace_fact_by_text("coffee", "x") == "ambiguous"


async def test_remove_by_text_not_found(isolated_memory: MemoryManager):
    assert await isolated_memory.remove_fact_by_text("nonexistent") == "not_found"


# ── Review op parsing ──────────────────────────────────────────────────


def test_parse_review_ops_valid():
    raw = (
        '{"operations":[{"action":"add","fact":"has a dog named Biscuit",'
        '"category":"relationship","confidence":0.9},'
        '{"action":"replace","fact":"lives in Osaka","old":"lives in Tokyo"},'
        '{"action":"remove","old":"vegetarian"}]}'
    )
    ops = _parse_review_json(raw)
    assert [o["action"] for o in ops] == ["add", "replace", "remove"]
    assert ops[1]["old"] == "lives in Tokyo"


def test_parse_review_ops_drops_invalid():
    raw = (
        '{"operations":['
        '{"action":"add"},'                       # add without fact
        '{"action":"replace","fact":"x"},'        # replace without old
        '{"action":"remove"},'                    # remove without old
        '{"action":"explode","fact":"x"},'        # unknown action
        '"not-a-dict",'
        '{"action":"add","fact":"valid one","category":"weird","confidence":9}]}'
    )
    ops = _parse_review_json(raw)
    assert len(ops) == 1
    assert ops[0]["fact"] == "valid one"
    assert ops[0]["category"] == "general"   # invalid category coerced
    assert ops[0]["confidence"] == 1.0       # clamped


def test_parse_review_ops_markdown_fences():
    raw = '```json\n{"operations":[{"action":"add","fact":"likes tea"}]}\n```'
    assert len(_parse_review_json(raw)) == 1


def test_parse_review_garbage_returns_empty():
    assert _parse_review_json("total nonsense") == []


# ── Delta application ──────────────────────────────────────────────────


async def test_apply_review_ops_full_cycle(isolated_memory: MemoryManager):
    await isolated_memory.store_fact("lives in Tokyo")
    await isolated_memory.store_fact("is vegetarian")

    counts = await isolated_memory.apply_review_ops(
        [
            {"action": "add", "fact": "has a dog named Biscuit", "old": "",
             "category": "relationship", "confidence": 0.9},
            {"action": "replace", "fact": "lives in Osaka", "old": "Tokyo",
             "category": "identity", "confidence": 1.0},
            {"action": "remove", "fact": "", "old": "vegetarian",
             "category": "general", "confidence": 1.0},
        ]
    )
    assert counts == {"added": 1, "replaced": 1, "removed": 1, "skipped": 0}
    facts = set(await isolated_memory.get_facts_raw())
    assert facts == {"has a dog named Biscuit", "lives in Osaka"}


async def test_apply_review_ops_dedupes_adds(isolated_memory: MemoryManager):
    await isolated_memory.store_fact("likes jazz music")
    counts = await isolated_memory.apply_review_ops(
        [{"action": "add", "fact": "likes jazz", "old": "",
          "category": "preference", "confidence": 1.0}]
    )
    assert counts["skipped"] == 1
    assert len(await isolated_memory.get_facts_raw()) == 1


async def test_apply_review_ops_ambiguous_target_is_skipped(isolated_memory: MemoryManager):
    await isolated_memory.store_fact("coffee in the morning")
    await isolated_memory.store_fact("coffee after lunch")
    counts = await isolated_memory.apply_review_ops(
        [{"action": "remove", "fact": "", "old": "coffee",
          "category": "general", "confidence": 1.0}]
    )
    assert counts["skipped"] == 1
    assert len(await isolated_memory.get_facts_raw()) == 2  # nothing guessed


async def test_review_recent_turns_survives_llm_failure(
    isolated_memory: MemoryManager, monkeypatch: pytest.MonkeyPatch
):
    async def boom(*a, **k):
        raise RuntimeError("no api key")

    import yumii.agent.fact_extractor as fx

    monkeypatch.setattr(fx, "review_facts", boom)
    counts = await isolated_memory.review_recent_turns(
        [{"role": "user", "content": "hi"}], "s1"
    )
    assert counts["added"] == 0  # swallowed, never raises


# ── The manage_memory tool ─────────────────────────────────────────────


async def test_tool_add(tool_memory: MemoryManager):
    from yumii.tools.memory_tool import manage_memory

    out = await manage_memory.ainvoke(
        {"action": "add", "fact": "user's birthday is March 3rd", "category": "identity"}
    )
    assert "Saved" in out
    assert await tool_memory.get_facts_raw() == ["user's birthday is March 3rd"]


async def test_tool_add_near_duplicate_redirects_to_replace(tool_memory: MemoryManager):
    from yumii.tools.memory_tool import manage_memory

    await tool_memory.store_fact("user's birthday is March 3rd")
    out = await manage_memory.ainvoke(
        {"action": "add", "fact": "user's birthday is March 3rd"}
    )
    assert "replace" in out.lower()
    assert len(await tool_memory.get_facts_raw()) == 1


async def test_tool_replace(tool_memory: MemoryManager):
    from yumii.tools.memory_tool import manage_memory

    await tool_memory.store_fact("user's birthday is March 5th")
    out = await manage_memory.ainvoke(
        {"action": "replace", "old_text": "birthday", "fact": "user's birthday is March 3rd"}
    )
    assert "Updated" in out
    assert await tool_memory.get_facts_raw() == ["user's birthday is March 3rd"]


async def test_tool_remove(tool_memory: MemoryManager):
    from yumii.tools.memory_tool import manage_memory

    await tool_memory.store_fact("is allergic to peanuts")
    out = await manage_memory.ainvoke({"action": "remove", "old_text": "peanuts"})
    assert "Forgotten" in out
    assert await tool_memory.get_facts_raw() == []


async def test_tool_ambiguous_asks_for_more(tool_memory: MemoryManager):
    from yumii.tools.memory_tool import manage_memory

    await tool_memory.store_fact("coffee in the morning")
    await tool_memory.store_fact("coffee after lunch")
    out = await manage_memory.ainvoke({"action": "remove", "old_text": "coffee"})
    assert "Several" in out
    assert len(await tool_memory.get_facts_raw()) == 2


async def test_tool_registered_as_ungated_write():
    import importlib

    import yumii.tools.memory_tool as mt
    from yumii.tools.policy import ToolCategory
    from yumii.tools.registry import registry

    registry.unregister("manage_memory")
    importlib.reload(mt)
    policy = registry.get_policy("manage_memory")
    assert policy.category is ToolCategory.WRITE
    assert policy.requires_confirmation is False


# ── Engine buffer logic ────────────────────────────────────────────────


async def test_engine_flush_fires_review_and_clears_buffer(monkeypatch):
    from yumii.core.engine import YumiiEngine
    from yumii.core import engine as engine_module

    calls = []

    async def fake_review(turns, session_id):
        calls.append((list(turns), session_id))

    monkeypatch.setattr(
        engine_module.memory_manager, "review_recent_turns", fake_review
    )

    e = YumiiEngine.__new__(YumiiEngine)
    e.active_session_id = "s1"
    e._memory_turn_buffer = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
    e._flush_memory_review()
    assert e._memory_turn_buffer == []
    await asyncio.sleep(0)  # let the created task run
    assert calls == [([{"role": "user", "content": "hi"},
                       {"role": "assistant", "content": "hello"}], "s1")]

    e._flush_memory_review()  # empty buffer → no second call
    await asyncio.sleep(0)
    assert len(calls) == 1
