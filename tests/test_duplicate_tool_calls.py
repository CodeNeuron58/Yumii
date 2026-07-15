"""Duplicate tool-call dedupe in the gated tools node.

Some models (minimax, llama) emit the same tool call several times in
one message. Only the first may execute — a duplicated send-email would
fire N times, and gated duplicates would stack N confirmation popups —
but every tool_call_id must still get a ToolMessage so the history
stays valid.
"""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import END, MessagesState, StateGraph

from yumii.agent.graph import _build_gated_tools_node, set_confirmation_hook

pytestmark = pytest.mark.asyncio

CALLS: list[dict] = []


@tool
def send_email(to: str, body: str) -> str:
    """Send an email (test double — counts invocations)."""
    CALLS.append({"to": to, "body": body})
    return f"sent to {to}"


@pytest.fixture(autouse=True)
def _reset():
    CALLS.clear()
    set_confirmation_hook(None)
    yield
    set_confirmation_hook(None)


def _compile_tools_graph(tools: list):
    """Wrap the gated node in a minimal compiled graph — ToolNode needs
    the LangGraph runtime context that direct invocation doesn't provide."""
    g = StateGraph(MessagesState)
    g.add_node("tools", _build_gated_tools_node(tools))
    g.set_entry_point("tools")
    g.add_edge("tools", END)
    return g.compile()


def _state_with_calls(calls: list[dict]) -> dict:
    return {
        "messages": [
            HumanMessage(content="email bob"),
            AIMessage(content="", tool_calls=calls),
        ]
    }


async def test_identical_calls_execute_once():
    graph = _compile_tools_graph([send_email])
    args = {"to": "bob@x.com", "body": "hi"}
    state = _state_with_calls(
        [
            {"name": "send_email", "args": args, "id": "c1"},
            {"name": "send_email", "args": dict(args), "id": "c2"},
            {"name": "send_email", "args": dict(args), "id": "c3"},
        ]
    )
    result = await graph.ainvoke(state)

    assert len(CALLS) == 1  # the email went out exactly once
    msgs = result["messages"]
    answered = {m.tool_call_id for m in msgs if isinstance(m, ToolMessage)}
    assert answered == {"c1", "c2", "c3"}  # every id answered
    dup_contents = [
        m.content for m in msgs
        if isinstance(m, ToolMessage) and m.tool_call_id in ("c2", "c3")
    ]
    assert all("Duplicate" in c for c in dup_contents)


async def test_different_args_are_not_deduped():
    graph = _compile_tools_graph([send_email])
    state = _state_with_calls(
        [
            {"name": "send_email", "args": {"to": "bob@x.com", "body": "hi"}, "id": "c1"},
            {"name": "send_email", "args": {"to": "amy@x.com", "body": "hi"}, "id": "c2"},
        ]
    )
    await graph.ainvoke(state)
    assert len(CALLS) == 2  # two genuinely different sends both run


async def test_gated_duplicates_prompt_only_once(monkeypatch):
    """Duplicates are dropped BEFORE the HITL gate — one popup, not three."""
    from yumii.core import config

    monkeypatch.setattr(config.settings, "hitl_mode", "always")

    prompts: list[str] = []

    async def hook(request_id, tool_name, tool_args):
        prompts.append(tool_name)
        return True

    set_confirmation_hook(hook)
    graph = _compile_tools_graph([send_email])
    args = {"to": "bob@x.com", "body": "hi"}
    state = _state_with_calls(
        [
            {"name": "send_email", "args": args, "id": "c1"},
            {"name": "send_email", "args": dict(args), "id": "c2"},
        ]
    )
    result = await graph.ainvoke(state)

    assert prompts == ["send_email"]  # user asked exactly once
    assert len(CALLS) == 1
    answered = {
        m.tool_call_id
        for m in result["messages"]
        if isinstance(m, ToolMessage)
    }
    assert answered == {"c1", "c2"}
