"""Tests for the searchable transcript (FTS5) and the recall tool.

Uses a temporary database — never touches the user's real ~/.yumii.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio

from yumii.core import memory_db, transcript
from yumii.tools.session_search_tool import search_past_conversations

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Redirect the memory DB to a temporary file for the test."""
    test_db = tmp_path / "test_memory.db"
    monkeypatch.setattr(memory_db, "MEMORY_DIR", tmp_path)
    monkeypatch.setattr(memory_db, "DB_PATH", test_db)
    await memory_db.init_db()
    return test_db


async def _seed(session_id: str, name: str, turns: list[tuple[str, str]]):
    await memory_db.execute(
        "INSERT INTO sessions (id, name) VALUES (?, ?)", (session_id, name)
    )
    for user, assistant in turns:
        await transcript.record_turn(session_id, user, assistant)


# ── Schema ─────────────────────────────────────────────────────────────


async def test_schema_has_messages_and_fts(isolated_db):
    rows = await memory_db.fetchall(
        "SELECT name FROM sqlite_master WHERE type IN ('table','trigger')"
    )
    names = {r["name"] for r in rows}
    assert "messages" in names
    assert "messages_fts" in names
    assert "messages_after_insert" in names
    assert "messages_after_delete" in names


# ── Recording + search ─────────────────────────────────────────────────


async def test_record_and_search_roundtrip(isolated_db):
    await _seed("s1", "Trip planning", [
        ("I'm planning a trip to Kyoto in October", "Kyoto in autumn sounds lovely!"),
    ])
    hits = await transcript.search("kyoto trip")
    assert len(hits) == 1
    assert hits[0].session_name == "Trip planning"
    assert "Kyoto" in hits[0].window[0]["content"]


async def test_porter_stemming_matches_word_forms(isolated_db):
    await _seed("s1", "Chat", [
        ("I was running late for the meeting again", "Mornings are hard!"),
    ])
    # Query "run" must match stored "running" via porter stemming.
    hits = await transcript.search("run")
    assert len(hits) == 1


async def test_and_falls_back_to_or(isolated_db):
    await _seed("s1", "Chat", [
        ("my dog is called Biscuit", "Biscuit is a great name!"),
    ])
    # "biscuit spaceship" — AND finds nothing, OR should still find the dog.
    hits = await transcript.search("biscuit spaceship")
    assert len(hits) == 1
    assert "Biscuit" in hits[0].window[0]["content"]


async def test_search_dedupes_to_best_hit_per_session(isolated_db):
    await _seed("s1", "Chat", [
        ("tell me about python", "Python is a language."),
        ("more python please", "More Python it is."),
        ("python again", "Always Python."),
    ])
    hits = await transcript.search("python")
    assert len(hits) == 1  # one session → one hit, not three


async def test_search_ranks_across_sessions(isolated_db):
    await _seed("s1", "Cooking", [("how do I make ramen", "Boil the broth first.")])
    await _seed("s2", "Coding", [("my ramen timer app crashed", "Show me the error?")])
    hits = await transcript.search("ramen")
    assert len(hits) == 2
    assert {h.session_id for h in hits} == {"s1", "s2"}


async def test_malicious_fts_syntax_is_neutralized(isolated_db):
    await _seed("s1", "Chat", [("hello there", "hi!")])
    # Unbalanced quotes / operators would crash raw FTS5 MATCH.
    for evil in ('"unbalanced', "NEAR(", "a AND OR b", "col:filter*", "-—…"):
        await transcript.search(evil)  # must not raise


async def test_empty_query_returns_nothing(isolated_db):
    assert await transcript.search("...") == []


# ── Window + browse + delete ───────────────────────────────────────────


async def test_window_around_returns_surrounding_messages(isolated_db):
    await _seed("s1", "Chat", [
        (f"question {i}", f"answer {i}") for i in range(5)
    ])
    hits = await transcript.search("question 2")
    anchor = hits[0].message_id
    window = await transcript.window_around("s1", anchor, span=2)
    contents = [m["content"] for m in window]
    assert "question 2" in " ".join(contents)
    assert 3 <= len(window) <= 5  # 2 before + anchor + 2 after


async def test_recent_sessions_browse(isolated_db):
    await _seed("s1", "First chat", [("hello world", "hi!")])
    await _seed("s2", "Second chat", [("goodbye moon", "see you!")])
    sessions = await transcript.recent_sessions()
    assert len(sessions) == 2
    assert sessions[0]["opened_with"] in ("hello world", "goodbye moon")


async def test_deleted_session_leaves_no_trace_in_search(isolated_db):
    await _seed("s1", "Secret", [("my secret password hint is walrus", "Noted.")])
    assert len(await transcript.search("walrus")) == 1
    await transcript.delete_session_messages("s1")
    assert await transcript.search("walrus") == []


async def test_backfill_gate_is_empty(isolated_db):
    assert await transcript.is_empty() is True
    await _seed("s1", "Chat", [("hi", "hello")])
    assert await transcript.is_empty() is False


# ── The tool's three shapes ────────────────────────────────────────────


async def test_tool_discover_shape(isolated_db):
    await _seed("s1", "Movie night", [
        ("let's watch Spirited Away on friday", "Great pick for movie night!"),
    ])
    out = await search_past_conversations.ainvoke({"query": "spirited away"})
    assert "Movie night" in out
    assert "session_id=s1" in out
    assert "Spirited Away" in out


async def test_tool_scroll_shape(isolated_db):
    await _seed("s1", "Chat", [("alpha", "beta"), ("gamma", "delta")])
    row = await memory_db.fetchone(
        "SELECT id FROM messages WHERE content = 'gamma'"
    )
    out = await search_past_conversations.ainvoke(
        {"session_id": "s1", "message_id": row["id"]}
    )
    assert "gamma" in out and "beta" in out


async def test_tool_browse_shape(isolated_db):
    await _seed("s1", "Morning chat", [("good morning", "morning!")])
    out = await search_past_conversations.ainvoke({})
    assert "Morning chat" in out


async def test_tool_no_results_is_graceful(isolated_db):
    out = await search_past_conversations.ainvoke({"query": "zeppelin"})
    assert "No past conversation" in out


async def test_tool_registered_as_ungated_read():
    # test_tool_registry's autouse fixture clears the global registry, so
    # re-fire this module's import-time registration instead of trusting
    # suite ordering.
    import importlib

    import yumii.tools.session_search_tool as sst
    from yumii.tools.policy import ToolCategory
    from yumii.tools.registry import registry

    registry.unregister("search_past_conversations")
    importlib.reload(sst)

    policy = registry.get_policy("search_past_conversations")
    assert policy.category is ToolCategory.READ
    assert policy.requires_confirmation is False


# ── Unicode queries + time-boxed search ────────────────────────────────


async def test_unicode_query_finds_accented_text(isolated_db):
    """Regression: the tokenizer was ASCII-only, so accented queries silently
    returned nothing even though the FTS index (unicode61) had them."""
    await _seed("s-café", "Café planning", [
        ("on s'est retrouvés au café pour parler du projet", "Génial !"),
    ])
    hits = await transcript.search("café projet")
    assert len(hits) == 1
    assert hits[0].session_id == "s-café"


async def test_search_respects_since_days(isolated_db):
    """The recall tool's time box: old conversations are excluded, recent kept."""
    from datetime import datetime, timedelta, timezone

    def _ts(**kw):
        return (datetime.now(timezone.utc) - timedelta(**kw)).strftime(
            "%Y-%m-%d %H:%M:%S.%f"
        )

    await memory_db.execute(
        "INSERT INTO sessions (id, name) VALUES (?, ?)", ("s-old", "Old plan")
    )
    await transcript.record_many("s-old", [("user", "marathon training plan")], created_at=_ts(days=30))
    await _seed("s-new", "This week", [("marathon shoes arrived", "Nice!")])

    all_hits = await transcript.search("marathon")
    assert {h.session_id for h in all_hits} == {"s-old", "s-new"}

    recent = await transcript.search("marathon", since_days=7)
    assert {h.session_id for h in recent} == {"s-new"}


async def test_recall_tool_passes_the_time_box_through(isolated_db):
    await memory_db.execute(
        "INSERT INTO sessions (id, name) VALUES (?, ?)", ("s-old", "Old")
    )
    await transcript.record_many(
        "s-old", [("user", "python asyncio bug")], created_at="2020-01-01 00:00:00.000000"
    )

    recent = await search_past_conversations.ainvoke({"query": "python asyncio", "since_days": 7})
    assert "Found" not in recent  # the old hit is out of the window
    everything = await search_past_conversations.ainvoke({"query": "python asyncio"})
    assert "Found" in everything


async def test_chatty_session_cannot_starve_other_sessions(isolated_db):
    """Regression: the old LIMIT-then-dedupe order let one session with 60+
    matches return as the ONLY result for a query that matched dozens of
    conversations. Dedupe now happens before limiting."""
    await memory_db.execute(
        "INSERT INTO sessions (id, name) VALUES (?, ?)", ("s-chatty", "Chatty")
    )
    for i in range(65):
        sid = "s-chatty"
        await memory_db.execute(
            "INSERT INTO messages (session_id, role, content, created_at)"
            " VALUES (?, 'user', ?, '2026-01-01')",
            (sid, f"alpha note number {i}"),
        )
    await _seed("s-other", "Other chat", [("alpha exists here too", "Yep")])

    hits = await transcript.search("alpha")
    session_ids = {h.session_id for h in hits}
    assert {"s-chatty", "s-other"} <= session_ids
    assert hits[0].session_id == "s-chatty"  # best-ranked session first
