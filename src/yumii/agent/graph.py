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
    │ tools  │ (gated ToolNode — see _build_gated_tools_node)
    └────────┘
      │
      └────────► back to agent

The ``tools`` node is wrapped with a HITL confirmation gate. Tools
whose :class:`ToolPolicy.requires_confirmation` is ``True`` (and that
are not opted-out by ``settings.hitl_mode``) pause execution,
broadcast a ``confirmation_request`` event, and resume only when the
user approves (or the timeout fires). The gate is implemented in
:meth:`_build_gated_tools_node` so LangGraph itself stays oblivious
to the user / WS layer.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from yumii.agent.llm import get_agent_llm
from yumii.agent.nodes import check_personality_switch
from yumii.agent.synthesizer import synthesize
from yumii.core.config import settings
from yumii.core.logging import get_logger
from yumii.tools.registry import list_policies, list_tools, tools_requiring_confirmation

log = get_logger(__name__)

# LangGraph checkpoints live in their own SQLite file.
_CHECKPOINT_DB = Path.home() / ".yumii" / "memory" / "checkpoints.db"

# Request-size guards. Free-tier Groq rejects any single request over
# 12k tokens (413), and tool results (a fetched inbox!) persist into
# the checkpointed history, poisoning every later turn of the session.
_MAX_TOOL_RESULT_CHARS = 6000  # ≈1.5k tokens per tool result
_HISTORY_WINDOW = 20  # messages sent to the LLM (full history stays in the checkpoint)


def _truncate_tool_results(result: Any) -> Any:
    """Cap oversized ToolMessage contents before they enter the state."""
    messages = result.get("messages", []) if isinstance(result, dict) else []
    for m in messages:
        if not isinstance(m, ToolMessage):
            continue
        content = m.content if isinstance(m.content, str) else str(m.content)
        if len(content) > _MAX_TOOL_RESULT_CHARS:
            m.content = (
                content[:_MAX_TOOL_RESULT_CHARS]
                + "\n... [result truncated — too long for the conversation context]"
            )
            log.info(
                "tool_result_truncated", tool=m.name, original_chars=len(content)
            )
    return result


def _window_history(history: list) -> list:
    """Return the most recent slice of history for the LLM request.

    The checkpoint keeps everything; this only bounds what each request
    carries. The window never starts on an orphaned ToolMessage (a
    ToolMessage without its preceding tool-calling AIMessage is an API
    error on strict providers). Trade-off: when the window slides,
    the request prefix changes and provider caching misses once —
    fitting under the request cap beats a cache hit.
    """
    windowed = history[-_HISTORY_WINDOW:]
    while windowed and isinstance(windowed[0], ToolMessage):
        windowed = windowed[1:]
    return windowed


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
        turn_id: str
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

    # NOTE: no per-turn time message. The old layout injected "The
    # current time is 11:42 PM..." as the second message — before the
    # entire history — so the request prefix changed every minute and
    # provider prefix (KV) caching missed on every turn. Today's DATE
    # now lives at the tail of the system prompt (one cache break per
    # day); precise time is a ``get_current_time`` tool call away.

    # The HumanMessage ID must be stable across multiple agent passes
    # within the same turn (agent -> tools -> agent) so the
    # add_messages reducer dedupes the re-added message — but unique
    # across turns, or repeating the same phrase later would overwrite
    # the earlier history entry instead of appending. The engine mints
    # a per-turn UUID; the hash fallback covers direct invocations.
    turn_id: str = state.get("turn_id") or f"{session_id}_{hash(user_input)}"
    human_id = f"hum_{turn_id}"
    new_human = HumanMessage(content=user_input, id=human_id)
    messages: list = _window_history(list(history)) + [new_human]

    # ``BoundLLM.ainvoke`` prepends the system prompt itself.
    # Llama on Groq occasionally emits a malformed tool call and the
    # whole request 400s with ``tool_use_failed`` — retry once (usually
    # transient at temperature 0.7), then degrade to a spoken apology
    # instead of crashing the turn.
    try:
        response: AIMessage = await bound.ainvoke(messages)
    except Exception as e:
        if "tool_use_failed" not in str(e):
            raise
        log.warning("tool_call_generation_failed_retrying", error=str(e)[:300])
        try:
            response = await bound.ainvoke(messages)
        except Exception as e2:
            if "tool_use_failed" not in str(e2):
                raise
            log.error("tool_call_generation_failed_twice", error=str(e2)[:300])
            response = AIMessage(
                content=(
                    "Mm, I fumbled the controls trying to do that for you — "
                    "my tool call didn't go through. Ask me one more time?"
                )
            )

    # If the agent finished without calling a tool, run the synthesizer
    # to derive the YumiiResponse shape the engine expects.
    if not getattr(response, "tool_calls", None):
        yumii_resp = synthesize(response.content or "")
        # Each pass appends exactly one new AIMessage, so its ID only
        # needs to be unique — providers usually set one; this is the
        # fallback.
        if not response.id:
            response = AIMessage(
                content=response.content,
                id=f"ai_{uuid.uuid4().hex}",
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
            id=f"ai_{uuid.uuid4().hex}",
        )
    return {
        "messages": [new_human, response],
    }


# ----------------------------------------------------------------------
# Gated tools node (PR 4 — HITL confirmation)
# ----------------------------------------------------------------------


def _tool_needs_confirmation(tool_name: str) -> bool:
    """Return ``True`` if the given tool requires a user confirmation
    under the current :data:`settings.hitl_mode`.

    Modes:

    * ``"never"`` — never gate any tool.
    * ``"external"`` (default) — gate only tools whose policy says
      :attr:`ToolPolicy.requires_confirmation` is True (i.e. EXTERNAL
      by default).
    * ``"always"`` — gate every tool call.
    """
    mode = (settings.hitl_mode or "external").lower()
    if mode == "never":
        return False
    if mode == "always":
        return True
    # "external" (or any unrecognised value — fail safe to external)
    return tool_name in set(tools_requiring_confirmation())


def _build_gated_tools_node(tools: list) -> Any:
    """Wrap LangGraph's prebuilt :class:`ToolNode` with a HITL gate.

    The returned callable mirrors the ToolNode signature: it receives
    the agent's state, inspects the last AIMessage's ``tool_calls``,
    and for each one whose policy demands a confirmation it pauses
    execution and asks the engine (via the module-level
    :data:`_gated_tools_hook`) to wait for the user's reply.

    If the user approves, the tool runs normally. If they deny, the
    timeout fires, or the user barge-ins, a synthetic
    :class:`ToolMessage` is returned to the LLM so the conversation
    can continue gracefully ("OK, I won't do that.").
    """
    inner = ToolNode(tools)

    async def gated_tools_node(state: dict[str, Any]) -> dict[str, Any]:
        messages = list(state.get("messages") or [])
        # Find the most recent AIMessage with tool_calls. The LangGraph
        # ``tools_condition`` guarantees this is the last message when
        # we enter this node, but we search defensively.
        last_ai: AIMessage | None = None
        for m in reversed(messages):
            if isinstance(m, AIMessage) and getattr(m, "tool_calls", None):
                last_ai = m
                break
        if last_ai is None:
            return _truncate_tool_results(await inner.ainvoke(state))

        hook = _gated_tools_hook.get("fn")
        denied_messages: list[ToolMessage] = []
        approved_calls: list[dict] = []

        for call in last_ai.tool_calls:
            name = call.get("name", "")
            args = call.get("args", {}) or {}
            call_id = call.get("id", "")
            if not _tool_needs_confirmation(name):
                # Not gated. Let the inner node handle it.
                approved_calls.append(call)
                continue

            # Gated: ask the engine's hook.
            approved = False
            if hook is not None:
                request_id = uuid.uuid4().hex
                try:
                    approved = await hook(
                        request_id=request_id,
                        tool_name=name,
                        tool_args=args,
                    )
                except Exception as e:
                    log.error(
                        "confirmation_hook_error",
                        tool=name,
                        error=str(e),
                        exc_info=True,
                    )
                    approved = False

            if approved:
                approved_calls.append(call)
            else:
                denied_messages.append(
                    ToolMessage(
                        content="User declined to run this tool.",
                        tool_call_id=call_id,
                        name=name,
                    )
                )

        if not denied_messages:
            # No denials — let the inner node dispatch everything.
            return _truncate_tool_results(await inner.ainvoke(state))

        if not approved_calls:
            # All gated calls were denied.
            return {"messages": denied_messages}

        # Mixed: run the inner node for the approved subset, then
        # append the denial messages so every tool_call_id has a
        # matching ToolMessage in the history.
        trimmed_ai = AIMessage(
            content=last_ai.content,
            tool_calls=approved_calls,
            id=last_ai.id,
        )
        sub_state = {**state, "messages": messages[:-1] + [trimmed_ai]}
        inner_result = _truncate_tool_results(await inner.ainvoke(sub_state))
        inner_messages = (
            inner_result.get("messages", [])
            if isinstance(inner_result, dict)
            else []
        )
        return {"messages": list(inner_messages) + denied_messages}

    return gated_tools_node


# Module-level slot for the engine to inject its HITL hook. The
# graph builder doesn't know about the engine, so we use this
# indirection: the engine calls :func:`set_confirmation_hook` at
# startup, and :func:`_build_gated_tools_node` reads the hook on
# every call.
_gated_tools_hook: dict[str, Any] = {"fn": None}


def set_confirmation_hook(fn) -> None:
    """Register the engine's HITL confirmation hook.

    The hook is awaited with ``(request_id, tool_name, tool_args)``
    and must return ``True`` (approved) or ``False`` (denied /
    timed out). Pass ``None`` to clear it.
    """
    _gated_tools_hook["fn"] = fn


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
    workflow.add_node("tools", _build_gated_tools_node(tools))

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
