"""Reasoning graph definition for Yumii.

Defines the LangGraph workflow that orchestrates the LLM interaction loop
and maintains the conversational state using **persistent** SQLite checkpoints.

The graph is a classic ReAct-style loop:

.. code-block:: text

    START
      │
      ▼
    ┌────────┐   no tool calls    ┌──────┐
    │ agent  │ ─────────────────► │ END  │
    └────────┘                    └──────┘
      │ tool calls
      ▼
    ┌────────┐
    │ tools  │ (ToolNode — prebuilt dispatcher)
    └────────┘
      │
      └────────► back to agent

The graph is **already shaped for HITL confirmation gates**: the
``tools`` node is a natural pause point. PR 4 will add
``interrupt_before=["tools"]`` and an engine handler that emits a
``confirmation_request`` to the browser and waits for the user's
response. For now the graph runs to completion in a single
``ainvoke`` call, matching the engine's pre-v1.0 contract.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from yumii.agent.llm import get_agent_llm
from yumii.agent.nodes import check_personality_switch
from yumii.agent.synthesizer import synthesize
from yumii.core.logging import get_logger
from yumii.tools.registry import list_policies, list_tools

log = get_logger(__name__)

# LangGraph checkpoints live in their own SQLite file.
_CHECKPOINT_DB = Path.home() / ".yumii" / "memory" / "checkpoints.db"


def _build_state_class() -> type:
    """Combine :class:`MessagesState` with Yumii's MainState fields.

    We need both the standard ``messages`` reducer (so ``add_messages``
    works) and the Yumii-specific fields (``input``, ``response``,
    ``expression``, ``motion``, ``session_id``, ``session_name``,
    ``user_facts``) that the engine writes into the state on every turn.
    """

    class YumiiMainState(MessagesState, total=False):
        """Yumii's full graph state. Inherits ``messages`` from MessagesState."""

        # ``messages`` is inherited from MessagesState with the
        # ``add_messages`` reducer.
        input: str
        response: str
        expression: str
        motion: str
        session_id: str
        session_name: str
        user_facts: list[str]

    return YumiiMainState


# Module-level schema for the graph. Tests that need isolation can
# import this and use it directly.
YumiiState: type = _build_state_class()


async def agent_node(state: dict[str, Any]) -> dict[str, Any]:
    """Run the LLM with bound tools and return its decision.

    The LLM may either:
      * emit a plain ``AIMessage`` (no tool calls) — we route to END.
      * emit an ``AIMessage`` with ``tool_calls`` — we route to ``tools``.

    Personality switching is handled in-place by rewriting the user's
    input (the model sees a system-prompt-friendly version of the
    request and acknowledges the switch in style).

    On the **final** turn (no tool calls), we also run the synthesizer
    to derive ``expression`` and ``motion`` from the agent text. PR 3
    replaces the placeholder synthesizer with a heuristic classifier.
    """
    user_input: str = state.get("input", "")
    history: list = state.get("messages", []) or []
    session_id: str = state.get("session_id", "")
    session_name: str = state.get("session_name", "")
    facts: list[str] = state.get("user_facts", []) or []

    log.debug("agent_node_start", text=user_input)

    is_switch, new_personality = check_personality_switch(user_input)
    if is_switch:
        from yumii.core.global_config import update_global_config

        update_global_config("PERSONALITY", new_personality)
        user_input = (
            f"I want you to become {new_personality}. "
            "Acknowledge this personality switch warmly in your new style."
        )

    # Build the LLM (with tools bound) for the active personality.
    facts_text = "\n".join(f"  - {f}" for f in facts)
    bound = get_agent_llm(
        session_id=session_id,
        session_name=session_name,
        user_facts=facts_text or None,
    )

    # Inject the current time as ephemeral context. The model still has
    # the ``get_current_time`` tool for timezones, but for the common
    # case "what time is it?" this saves a round-trip.
    time_msg = SystemMessage(
        content=(
            f"The current time is "
            f"{datetime.datetime.now().strftime('%I:%M %p on %A, %B %d, %Y')}. "
            f"Use this information if the user asks about the time."
        )
    )
    # Use a deterministic ID for the HumanMessage so the add_messages
    # reducer deduplicates it across multiple agent passes within the
    # same turn (agent -> tools -> agent). Without this, the second
    # pass would see a HumanMessage in its history AND add a new one.
    human_id = f"hum_{session_id}_{hash(user_input)}"
    new_human = HumanMessage(content=user_input, id=human_id)
    messages: list = [time_msg] + list(history) + [new_human]

    # ``BoundLLM.ainvoke`` prepends the cached system prompt itself.
    response: AIMessage = await bound.ainvoke(messages)

    # If the agent finished without calling a tool, run the synthesizer
    # to derive the YumiiResponse shape the engine expects.
    if not getattr(response, "tool_calls", None):
        yumii_resp = synthesize(response.content or "")
        # Tag the AIMessage with a stable id so add_messages dedupes
        # across passes within a turn.
        if not response.id:
            response = AIMessage(
                content=response.content,
                id=f"ai_{session_id}_{hash(user_input)}_{hash(response.content or '')}",
            )
        return {
            "messages": [new_human, response],
            "response": yumii_resp.response_text,
            "expression": yumii_resp.expression,
            "motion": yumii_resp.motion,
        }

    # Otherwise, return the AIMessage with tool_calls; routing will
    # send us to the ``tools`` node. The HumanMessage is appended
    # here so the message history is consistent on the next turn.
    if not response.id:
        response = AIMessage(
            content=response.content,
            tool_calls=response.tool_calls,
            id=f"ai_{session_id}_{hash(user_input)}_tools",
        )
    return {
        "messages": [new_human, response],
    }


async def build_graph(checkpointer: AsyncSqliteSaver | None = None) -> Any:
    """Build and return the compiled LangGraph for Yumii's reasoning engine.

    Uses :class:`AsyncSqliteSaver` so conversation history survives
    server restarts. Each session gets its own ``thread_id`` checkpoint
    namespace automatically.

    The ``tools`` node runs LangGraph's prebuilt :class:`ToolNode`, which
    dispatches to the right tool based on the ``AIMessage.tool_calls``
    list. PR 4 will add ``interrupt_before=["tools"]`` plus an engine
    handler that emits a ``confirmation_request`` to the browser and
    waits for the user's response.
    """
    tools = list_tools()
    if not tools:
        log.warning("graph_build_no_tools", hint="registry empty — agent will never call tools")

    log.info(
        "langgraph_building",
        tool_count=len(tools),
        tools=[t.name for t in tools],
        policies={n: p.category.value for n, p in list_policies().items()},
    )

    workflow = StateGraph(YumiiState)

    # Nodes
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", ToolNode(tools))

    # Edges
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges(
        "agent",
        tools_condition,
        {"tools": "tools", END: END},
    )
    workflow.add_edge("tools", "agent")

    if checkpointer is None:
        _CHECKPOINT_DB.parent.mkdir(parents=True, exist_ok=True)
        async with AsyncSqliteSaver.from_conn_string(str(_CHECKPOINT_DB)) as saver:
            return workflow.compile(checkpointer=saver)
    return workflow.compile(checkpointer=checkpointer)


__all__ = [
    "build_graph",
    "agent_node",
    "YumiiState",
    "_CHECKPOINT_DB",
]
