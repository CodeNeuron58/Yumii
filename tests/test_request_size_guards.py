"""Tests for the request-size guards added after the free-tier 413.

Groq's free tier rejects any single request over 12k tokens. Three
guards keep requests bounded: curated Composio tool subsets, tool
result truncation, and a history window.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from yumii.agent.graph import (
    _HISTORY_WINDOW,
    _MAX_TOOL_RESULT_CHARS,
    _truncate_tool_results,
    _window_history,
)
from yumii.tools.composio_loader import _CURATED_TOOLS, _resolve_tool_selection


# ── Curated tool selection ─────────────────────────────────────────────


def test_gmail_uses_curated_subset():
    slugs, uncurated = _resolve_tool_selection(["GMAIL"], None)
    assert slugs == _CURATED_TOOLS["GMAIL"]
    assert uncurated == []


def test_user_override_beats_curation():
    slugs, uncurated = _resolve_tool_selection(
        ["GMAIL"], {"GMAIL": ["gmail_fetch_emails"]}
    )
    assert slugs == ["GMAIL_FETCH_EMAILS"]
    assert uncurated == []


def test_unknown_toolkit_goes_to_limited_bucket():
    slugs, uncurated = _resolve_tool_selection(["GMAIL", "SPOTIFY"], None)
    assert "SPOTIFY" in uncurated
    assert slugs == _CURATED_TOOLS["GMAIL"]


def test_bad_override_shape_falls_back():
    slugs, uncurated = _resolve_tool_selection(["SPOTIFY"], {"SPOTIFY": "not-a-list"})
    assert slugs == []
    assert uncurated == ["SPOTIFY"]


# ── Tool result truncation ─────────────────────────────────────────────


def test_oversized_tool_result_is_truncated():
    huge = "x" * (_MAX_TOOL_RESULT_CHARS * 5)
    result = {"messages": [ToolMessage(content=huge, tool_call_id="1", name="gmail")]}
    out = _truncate_tool_results(result)
    content = out["messages"][0].content
    assert len(content) < _MAX_TOOL_RESULT_CHARS + 100
    assert "truncated" in content


def test_small_tool_result_untouched():
    result = {"messages": [ToolMessage(content="3 emails found", tool_call_id="1", name="gmail")]}
    out = _truncate_tool_results(result)
    assert out["messages"][0].content == "3 emails found"


def test_non_tool_messages_ignored():
    result = {"messages": [AIMessage(content="y" * 99999)]}
    out = _truncate_tool_results(result)
    assert len(out["messages"][0].content) == 99999


# ── History window ─────────────────────────────────────────────────────


def test_short_history_passes_through():
    history = [HumanMessage(content=f"m{i}") for i in range(5)]
    assert _window_history(history) == history


def test_long_history_is_windowed():
    history = [HumanMessage(content=f"m{i}") for i in range(100)]
    windowed = _window_history(history)
    assert len(windowed) == _HISTORY_WINDOW
    assert windowed[-1].content == "m99"


def test_window_never_starts_on_orphan_tool_message():
    # Arrange the cut so the window would open on ToolMessages.
    history = [HumanMessage(content=f"m{i}") for i in range(_HISTORY_WINDOW - 1)]
    history += [
        AIMessage(content="", tool_calls=[{"name": "t", "args": {}, "id": "1"}]),
        ToolMessage(content="result-1", tool_call_id="1", name="t"),
        ToolMessage(content="result-2", tool_call_id="1", name="t"),
    ]
    history += [HumanMessage(content=f"tail{i}") for i in range(_HISTORY_WINDOW - 2)]
    windowed = _window_history(history)
    assert not isinstance(windowed[0], ToolMessage)
