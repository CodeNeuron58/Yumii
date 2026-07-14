"""Tests for the request-size guards and history hygiene.

Groq's free tier rejects any single request over 8-12k tokens, so Groq
gets tight budgets (curated Composio subsets, aggressive truncation, a
short history window). Every other provider gets generous budgets. The
window also repairs dangling tool calls so one interrupted turn can't
poison the session.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from yumii.agent.graph import (
    _GROQ_HISTORY_WINDOW,
    _GROQ_MAX_TOOL_RESULT_CHARS,
    _HISTORY_WINDOW,
    _MAX_TOOL_RESULT_CHARS,
    _repair_dangling_tool_calls,
    _request_budgets,
    _truncate_tool_results,
    _window_history,
)
from yumii.tools.composio_loader import _CURATED_TOOLS, _resolve_tool_selection


# ── Provider-aware budgets ─────────────────────────────────────────────


def test_groq_gets_tight_budgets(monkeypatch):
    from yumii.core import config

    monkeypatch.setattr(config.settings, "llm_provider", "Groq")
    assert _request_budgets() == (_GROQ_MAX_TOOL_RESULT_CHARS, _GROQ_HISTORY_WINDOW)


def test_other_providers_get_generous_budgets(monkeypatch):
    from yumii.core import config

    monkeypatch.setattr(config.settings, "llm_provider", "Ollama")
    assert _request_budgets() == (_MAX_TOOL_RESULT_CHARS, _HISTORY_WINDOW)


# ── Curated tool selection (Groq only) ─────────────────────────────────


def test_gmail_uses_curated_subset_when_curating():
    slugs, whole = _resolve_tool_selection(["GMAIL"], None, curate=True)
    assert slugs == _CURATED_TOOLS["GMAIL"]
    assert whole == []


def test_no_curation_loads_whole_toolkit():
    slugs, whole = _resolve_tool_selection(["GMAIL"], None, curate=False)
    assert slugs == []
    assert whole == ["GMAIL"]


def test_user_override_beats_curation():
    slugs, whole = _resolve_tool_selection(
        ["GMAIL"], {"GMAIL": ["gmail_fetch_emails"]}, curate=True
    )
    assert slugs == ["GMAIL_FETCH_EMAILS"]
    assert whole == []


def test_user_override_applies_even_without_curation():
    slugs, whole = _resolve_tool_selection(
        ["GMAIL"], {"GMAIL": ["gmail_fetch_emails"]}, curate=False
    )
    assert slugs == ["GMAIL_FETCH_EMAILS"]
    assert whole == []


def test_unknown_toolkit_goes_to_whole_bucket():
    slugs, whole = _resolve_tool_selection(["GMAIL", "SPOTIFY"], None, curate=True)
    assert "SPOTIFY" in whole
    assert slugs == _CURATED_TOOLS["GMAIL"]


def test_bad_override_shape_falls_back():
    slugs, whole = _resolve_tool_selection(
        ["SPOTIFY"], {"SPOTIFY": "not-a-list"}, curate=True
    )
    assert slugs == []
    assert whole == ["SPOTIFY"]


# ── Tool result truncation ─────────────────────────────────────────────


def test_oversized_tool_result_is_truncated():
    huge = "x" * 15000
    result = {"messages": [ToolMessage(content=huge, tool_call_id="1", name="gmail")]}
    out = _truncate_tool_results(result, max_chars=3000)
    content = out["messages"][0].content
    assert len(content) < 3000 + 100
    assert "truncated" in content


def test_small_tool_result_untouched():
    result = {"messages": [ToolMessage(content="3 emails found", tool_call_id="1", name="gmail")]}
    out = _truncate_tool_results(result, max_chars=3000)
    assert out["messages"][0].content == "3 emails found"


def test_non_tool_messages_ignored():
    result = {"messages": [AIMessage(content="y" * 99999)]}
    out = _truncate_tool_results(result, max_chars=3000)
    assert len(out["messages"][0].content) == 99999


# ── History window ─────────────────────────────────────────────────────


def test_short_history_passes_through():
    history = [HumanMessage(content=f"m{i}") for i in range(5)]
    assert _window_history(history, window=12) == history


def test_long_history_is_windowed():
    history = [HumanMessage(content=f"m{i}") for i in range(100)]
    windowed = _window_history(history, window=12)
    assert len(windowed) == 12
    assert windowed[-1].content == "m99"


def test_window_never_starts_on_orphan_tool_message():
    # Arrange the cut so the window would open on ToolMessages.
    window = 12
    history = [HumanMessage(content=f"m{i}") for i in range(window - 1)]
    history += [
        AIMessage(content="", tool_calls=[{"name": "t", "args": {}, "id": "1"}]),
        ToolMessage(content="result-1", tool_call_id="1", name="t"),
        ToolMessage(content="result-2", tool_call_id="1", name="t"),
    ]
    history += [HumanMessage(content=f"tail{i}") for i in range(window - 2)]
    windowed = _window_history(history, window=window)
    assert not isinstance(windowed[0], ToolMessage)


# ── Dangling tool-call repair ──────────────────────────────────────────


def test_dangling_tool_call_gets_synthetic_result():
    # An interrupted turn: tool was requested, no result ever landed.
    history = [
        HumanMessage(content="check my email"),
        AIMessage(content="", tool_calls=[{"name": "gmail", "args": {}, "id": "call-1"}]),
        HumanMessage(content="hello?"),
    ]
    repaired = _repair_dangling_tool_calls(history)
    tool_msgs = [m for m in repaired if isinstance(m, ToolMessage)]
    assert len(tool_msgs) == 1
    assert tool_msgs[0].tool_call_id == "call-1"
    assert "interrupted" in tool_msgs[0].content
    # The synthetic result sits directly after the tool-calling message.
    idx = next(i for i, m in enumerate(repaired) if isinstance(m, AIMessage))
    assert isinstance(repaired[idx + 1], ToolMessage)


def test_answered_tool_calls_are_untouched():
    history = [
        AIMessage(content="", tool_calls=[{"name": "t", "args": {}, "id": "1"}]),
        ToolMessage(content="done", tool_call_id="1", name="t"),
    ]
    assert _repair_dangling_tool_calls(history) == history


def test_partial_answers_only_repair_the_missing_call():
    history = [
        AIMessage(
            content="",
            tool_calls=[
                {"name": "a", "args": {}, "id": "1"},
                {"name": "b", "args": {}, "id": "2"},
            ],
        ),
        ToolMessage(content="done", tool_call_id="1", name="a"),
    ]
    repaired = _repair_dangling_tool_calls(history)
    ids = [m.tool_call_id for m in repaired if isinstance(m, ToolMessage)]
    assert sorted(ids) == ["1", "2"]


def test_window_repairs_dangling_calls():
    history = [
        HumanMessage(content="check my email"),
        AIMessage(content="", tool_calls=[{"name": "gmail", "args": {}, "id": "x"}]),
    ]
    windowed = _window_history(history, window=12)
    assert isinstance(windowed[-1], ToolMessage)
    assert windowed[-1].tool_call_id == "x"
