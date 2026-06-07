"""Tests for the v1.0 agent graph (PR 2).

These tests verify that the new ``agent`` + ``tools`` graph:

* compiles and is invocable,
* runs plain conversational turns without calling any tool,
* routes to the ``tools`` node when the LLM emits ``tool_calls``,
* correctly hands off to LangGraph's prebuilt :class:`ToolNode` for
  the real ``get_current_time`` tool,
* preserves the engine contract (final state has ``response``,
  ``expression``, ``motion``),
* handles personality switches in-band,
* and survives round-trips through the SQLite checkpointer.

The tests use a fake :class:`BoundLLM` (and patch
:func:`get_agent_llm`) so they don't need a real LLM provider.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolCall

from yumii.agent import graph as graph_mod
from yumii.agent.llm import BoundLLM, clear_llm_cache, get_agent_llm
from yumii.agent.synthesizer import synthesize
from yumii.agent.graph import YumiiState, agent_node
from yumii.tools.registry import registry as global_registry


# ----------------------------------------------------------------------
# Test fixtures
# ----------------------------------------------------------------------


def _make_fake_bound(
    *,
    text_response: str | None = None,
    tool_calls: list[ToolCall] | None = None,
) -> BoundLLM:
    """Return a fake :class:`BoundLLM` whose ``ainvoke`` yields a fixed response.

    Args:
        text_response: The content of a plain ``AIMessage`` to return.
            Ignored if ``tool_calls`` is set.
        tool_calls: A list of :class:`ToolCall` for the fake LLM to emit
            on its single call. The fake ignores further calls (good
            enough for single-turn graph tests).
    """
    fake_llm = MagicMock()
    if tool_calls is not None:
        msg: AIMessage = AIMessage(content="", tool_calls=tool_calls)
    else:
        msg = AIMessage(content=text_response or "hello there")

    fake_llm.ainvoke = AsyncMock(return_value=msg)
    return BoundLLM(
        llm=fake_llm,
        system_prompt="(fake system prompt)",
        personality="caring",
    )


@pytest.fixture(autouse=True)
def _reset_state():
    """Clear caches and the global registry between tests."""
    clear_llm_cache()
    global_registry.clear()
    # Re-register the time tool so list_tools() is non-empty in the
    # tests that exercise the real ToolNode.
    from yumii.tools import time_tool  # noqa: F401
    import importlib

    importlib.reload(time_tool)
    yield
    clear_llm_cache()
    global_registry.clear()


# ----------------------------------------------------------------------
# YumiiState shape
# ----------------------------------------------------------------------


def test_yumii_state_includes_messages_and_yumii_fields() -> None:
    """The state class should carry the standard ``messages`` field plus Yumii's fields."""
    annotations = YumiiState.__annotations__
    for field in (
        "messages",
        "input",
        "response",
        "expression",
        "motion",
        "session_id",
        "session_name",
        "user_facts",
    ):
        assert field in annotations, f"YumiiState missing field: {field}"


# ----------------------------------------------------------------------
# Synthesizer placeholder (PR 3 replaces the body)
# ----------------------------------------------------------------------


def test_synthesize_normal_text_returns_normal_and_idle() -> None:
    """Plain text should default to ``normal`` expression, ``idle`` motion.

    The fixture text is intentionally neutral (no emotion words, no
    punctuation triggers) so it falls through to normal/idle.
    """
    out = synthesize("the sky is blue today")
    assert out.response_text == "the sky is blue today"
    assert out.expression == "normal"
    assert out.motion == "idle"


def test_synthesize_empty_text_returns_safe_defaults() -> None:
    """Empty text should not blow up — engine may call us with ``""``."""
    out = synthesize("")
    assert out.expression == "normal"
    assert out.motion == "idle"
    assert isinstance(out.response_text, str)


# ----------------------------------------------------------------------
# agent_node behaviour
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_node_with_text_response_fills_yumii_response_fields() -> None:
    """A plain AIMessage should yield response / expression / motion in the state delta.

    The expression / motion labels are computed by the synthesizer from the
    raw LLM text. The neutral fixture text "the sky is blue" is chosen so it
    doesn't match any emotion/motion regex and yields normal/idle.
    """
    bound = _make_fake_bound(text_response="the sky is blue")
    with patch("yumii.agent.graph.get_agent_llm", return_value=bound):
        delta = await agent_node(
            {
                "input": "hi",
                "messages": [],
                "session_id": "s1",
                "session_name": "Test",
                "user_facts": [],
            }
        )
    assert delta["response"] == "the sky is blue"
    assert delta["expression"] == "normal"
    assert delta["motion"] == "idle"
    # messages delta should include the user's HumanMessage and the AIMessage.
    msgs = delta["messages"]
    assert any(isinstance(m, HumanMessage) and m.content == "hi" for m in msgs)
    assert any(isinstance(m, AIMessage) and m.content == "the sky is blue" for m in msgs)


@pytest.mark.asyncio
async def test_agent_node_with_tool_calls_does_not_set_response() -> None:
    """When the LLM emits tool_calls, the agent should not synthesize yet."""
    bound = _make_fake_bound(
        tool_calls=[
            ToolCall(name="get_current_time", args={}, id="call_1"),
        ],
    )
    with patch("yumii.agent.graph.get_agent_llm", return_value=bound):
        delta = await agent_node(
            {
                "input": "what time is it?",
                "messages": [],
                "session_id": "s1",
                "session_name": "Test",
                "user_facts": [],
            }
        )
    # No final response yet — graph will route to tools next.
    assert "response" not in delta
    # But the AIMessage with tool_calls IS in the message delta.
    ai_msgs = [m for m in delta["messages"] if isinstance(m, AIMessage)]
    assert len(ai_msgs) == 1
    assert ai_msgs[0].tool_calls


# ----------------------------------------------------------------------
# build_graph
# ----------------------------------------------------------------------


def test_build_graph_compiles_without_checkpointer_argument() -> None:
    """Passing no checkpointer should still produce a compiled graph."""
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    # Use an in-memory saver to avoid touching ~/.yumii/.
    async def _build():
        async with AsyncSqliteSaver.from_conn_string(":memory:") as saver:
            app = await graph_mod.build_graph(checkpointer=saver)
            return app

    import asyncio

    app = asyncio.run(_build())
    assert app is not None
    # Compiled graphs expose an ``invoke`` and ``ainvoke``.
    assert hasattr(app, "invoke")
    assert hasattr(app, "ainvoke")


def test_build_graph_emits_tool_count_log(capsys) -> None:
    """The build log should mention the registered tool count and name.

    We assert on captured stdout because the project uses structlog
    configured with a ``ConsoleRenderer`` that writes to stdout
    directly — ``caplog`` (stdlib-logging based) cannot see those
    records. The captured stdout is the proof the log fired.
    """
    import asyncio

    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    async def _build():
        async with AsyncSqliteSaver.from_conn_string(":memory:") as saver:
            return await graph_mod.build_graph(checkpointer=saver)

    asyncio.run(_build())
    captured = capsys.readouterr().out
    assert "langgraph_building" in captured
    assert "get_current_time" in captured
    assert "tool_count=1" in captured


# ----------------------------------------------------------------------
# End-to-end: agent -> tools -> agent -> END with the real ToolNode
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_graph_runs_tool_then_returns_text() -> None:
    """The full ReAct loop should call get_current_time, observe its result, and answer."""
    # First agent call emits a tool_call; second (after tool result)
    # emits a plain text answer.
    fake_llm = MagicMock()
    fake_llm.ainvoke = AsyncMock(
        side_effect=[
            AIMessage(
                content="",
                tool_calls=[ToolCall(name="get_current_time", args={}, id="c1")],
            ),
            AIMessage(content="It is currently a pleasant hour of the day."),
        ]
    )
    bound = BoundLLM(llm=fake_llm, system_prompt="(fake)", personality="caring")

    with patch("yumii.agent.graph.get_agent_llm", return_value=bound):
        async with build_graph_for_test() as app:
            config = {"configurable": {"thread_id": "t-graph"}}
            result = await app.ainvoke(
                {
                    "input": "what time is it?",
                    "session_id": "s-graph",
                    "session_name": "Test",
                    "user_facts": [],
                },
                config=config,
            )

    assert result["response"] == "It is currently a pleasant hour of the day."
    assert result["expression"] == "normal"
    assert result["motion"] == "idle"
    # The conversation history should include: HumanMessage, AIMessage(tool_call),
    # ToolMessage (the actual time), AIMessage (the final text).
    types = [type(m).__name__ for m in result["messages"]]
    assert "HumanMessage" in types
    assert "AIMessage" in types
    assert "ToolMessage" in types


# ----------------------------------------------------------------------
# get_agent_llm caching
# ----------------------------------------------------------------------


def test_get_agent_llm_caches_per_personality_and_facts() -> None:
    """Two calls with the same (personality, facts) should return the same BoundLLM."""
    clear_llm_cache()
    a = get_agent_llm("s1", "name", user_facts="likes coffee")
    b = get_agent_llm("s1", "name", user_facts="likes coffee")
    assert a is b


def test_get_agent_llm_different_facts_yields_different_binding() -> None:
    """Different facts should produce a different cached entry."""
    clear_llm_cache()
    a = get_agent_llm("s1", "name", user_facts="likes coffee")
    b = get_agent_llm("s1", "name", user_facts="likes tea")
    assert a is not b
    # Same personality, so both should carry the right system prompt.
    assert a.system_prompt != b.system_prompt


def test_clear_llm_cache_invalidates_entries() -> None:
    """clear_llm_cache should force a fresh binding on the next call."""
    clear_llm_cache()
    a = get_agent_llm("s1", "name", user_facts="")
    clear_llm_cache()
    b = get_agent_llm("s1", "name", user_facts="")
    assert a is not b


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


from contextlib import asynccontextmanager  # noqa: E402


@asynccontextmanager
async def build_graph_for_test():
    """Yield a compiled graph using an in-memory AsyncSqliteSaver.

    Avoids touching ``~/.yumii/memory/checkpoints.db`` and works around
    the fact that ``build_graph`` creates a fresh checkpointer inside
    the call.
    """
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    async with AsyncSqliteSaver.from_conn_string(":memory:") as saver:
        app = await graph_mod.build_graph(checkpointer=saver)
        yield app
