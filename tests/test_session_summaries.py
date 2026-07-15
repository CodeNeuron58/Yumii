"""Tests for session summaries + time sense (episodic memory).

Isolated DB + fake LLM throughout — no network, no real ~/.yumii.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import pytest_asyncio

from yumii.core import memory_db, summarizer, transcript
from yumii.core.summarizer import (
    build_session_context,
    humanize_ago,
    summarize_session,
)

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    test_db = tmp_path / "test_memory.db"
    monkeypatch.setattr(memory_db, "MEMORY_DIR", tmp_path)
    monkeypatch.setattr(memory_db, "DB_PATH", test_db)
    await memory_db.init_db()
    return test_db


class FakeLLM:
    def __init__(self, reply: str = "The user planned a trip to Kyoto."):
        self.reply = reply
        self.calls = 0

    async def ainvoke(self, messages):
        self.calls += 1

        class R:
            content = self.reply

        return R()


@pytest.fixture
def fake_llm(monkeypatch: pytest.MonkeyPatch):
    llm = FakeLLM()
    import yumii.agent.fact_extractor as fx

    monkeypatch.setattr(fx, "_get_extractor_llm", lambda: llm)
    return llm


def _ago(**kw) -> str:
    return (datetime.now(timezone.utc) - timedelta(**kw)).strftime(
        "%Y-%m-%d %H:%M:%S.%f"
    )


async def _seed_session(sid: str, name: str, last_active: str, turns=2):
    await memory_db.execute(
        "INSERT INTO sessions (id, name, created_at, last_active_at)"
        " VALUES (?, ?, ?, ?)",
        (sid, name, last_active, last_active),
    )
    for i in range(turns):
        await transcript.record_turn(sid, f"question {i}", f"answer {i}")


# ── humanize_ago ───────────────────────────────────────────────────────


def test_humanize_ago_buckets():
    assert humanize_ago(_ago(seconds=30)) == "just now"
    assert humanize_ago(_ago(minutes=5)) == "5 minutes ago"
    assert humanize_ago(_ago(hours=3)) == "3 hours ago"
    assert humanize_ago(_ago(hours=30)) == "yesterday"
    assert humanize_ago(_ago(days=4)) == "4 days ago"
    assert humanize_ago(_ago(days=21)) == "3 weeks ago"


def test_humanize_ago_degrades_gracefully():
    assert humanize_ago(None) == "a while ago"
    assert humanize_ago("not-a-timestamp") == "a while ago"
    # Second-resolution legacy rows (no microseconds) still parse.
    ts = (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
    assert humanize_ago(ts) == "3 days ago"


# ── summarize_session ──────────────────────────────────────────────────


async def test_summarize_writes_the_table(isolated_db, fake_llm):
    await _seed_session("s1", "Kyoto", _ago(days=1))
    out = await summarize_session("s1")
    assert out == "The user planned a trip to Kyoto."
    row = await memory_db.fetchone(
        "SELECT summary, message_count FROM session_summaries WHERE session_id='s1'"
    )
    assert row["summary"] == out
    assert row["message_count"] == 4  # 2 turns = 4 messages


async def test_summarize_watermark_skips_unchanged(isolated_db, fake_llm):
    await _seed_session("s1", "Kyoto", _ago(days=1))
    assert await summarize_session("s1") is not None
    assert fake_llm.calls == 1
    # No new messages → no second LLM call.
    assert await summarize_session("s1") is None
    assert fake_llm.calls == 1
    # New turn → re-summarizes (upsert).
    await transcript.record_turn("s1", "one more", "sure")
    assert await summarize_session("s1") is not None
    assert fake_llm.calls == 2


async def test_summarize_too_short_or_missing_is_noop(isolated_db, fake_llm):
    assert await summarize_session("ghost") is None
    assert await summarize_session("") is None
    assert fake_llm.calls == 0


async def test_summarize_llm_failure_returns_none(isolated_db, monkeypatch):
    await _seed_session("s1", "Kyoto", _ago(days=1))

    class Boom:
        async def ainvoke(self, m):
            raise RuntimeError("no key")

    import yumii.agent.fact_extractor as fx

    monkeypatch.setattr(fx, "_get_extractor_llm", lambda: Boom())
    assert await summarize_session("s1") is None  # swallowed


# ── build_session_context ──────────────────────────────────────────────


async def test_first_ever_conversation(isolated_db):
    await memory_db.execute(
        "INSERT INTO sessions (id, name) VALUES ('current', 'New Chat')"
    )
    ctx = await build_session_context("current")
    assert "very first conversation" in ctx


async def test_context_has_time_sense_and_recents(isolated_db, fake_llm):
    await _seed_session("old1", "Kyoto trip", _ago(days=2))
    await summarize_session("old1")
    await memory_db.execute(
        "INSERT INTO sessions (id, name) VALUES ('current', 'New Chat')"
    )
    ctx = await build_session_context("current")
    assert "You last spoke with them 2 days ago." in ctx
    assert 'Recent conversations:' in ctx
    assert '"Kyoto trip": The user planned a trip to Kyoto.' in ctx


async def test_context_excludes_current_session_from_recents(isolated_db, fake_llm):
    await _seed_session("current", "Live chat", _ago(minutes=1))
    await summarize_session("current")
    ctx = await build_session_context("current", include_current=False)
    assert "Live chat" not in ctx  # own summary not listed as a "recent"


async def test_include_current_adds_earlier_in_conversation(isolated_db, fake_llm):
    await _seed_session("old1", "Other", _ago(days=1))
    await _seed_session("current", "Live chat", _ago(minutes=1))
    await summarize_session("current")
    ctx = await build_session_context("current", include_current=True)
    assert "Earlier in this conversation: The user planned a trip to Kyoto." in ctx


async def test_recents_capped_at_three(isolated_db, fake_llm):
    for i in range(5):
        await _seed_session(f"s{i}", f"Chat {i}", _ago(days=i + 1))
        await summarize_session(f"s{i}")
    await memory_db.execute(
        "INSERT INTO sessions (id, name) VALUES ('current', 'New Chat')"
    )
    ctx = await build_session_context("current")
    assert ctx.count("- ") == 3


# ── Prompt assembly placement ──────────────────────────────────────────


def test_prompt_session_context_sits_between_date_and_facts():
    from yumii.agent.llm import _build_system_prompt

    prompt = _build_system_prompt(
        "caring",
        "  - likes jazz",
        session_context="You last spoke with them 2 days ago.",
    )
    date_pos = prompt.index("Today is ")
    ctx_pos = prompt.index("You last spoke with them")
    facts_pos = prompt.index("What you know about the user:")
    assert date_pos < ctx_pos < facts_pos


def test_prompt_without_context_is_unchanged_prefix():
    """session_context must only mutate the tail (cache safety)."""
    from yumii.agent.llm import _build_system_prompt

    without = _build_system_prompt("caring", None)
    with_ctx = _build_system_prompt(
        "caring", None, session_context="You last spoke with them yesterday."
    )
    assert with_ctx.startswith(without)


# ── Engine trigger cadence ─────────────────────────────────────────────


def test_refresh_interval_is_sane():
    assert summarizer.SUMMARY_REFRESH_MESSAGES >= 10  # not every turn
