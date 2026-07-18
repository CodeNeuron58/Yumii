"""Reasoning graph for Yumii: a ReAct-style agent → tools → agent loop over SQLite checkpoints.

The ``tools`` node is wrapped in a HITL confirmation gate (see
:func:`_build_gated_tools_node`) so LangGraph stays oblivious to the WS layer.
"""

from __future__ import annotations

import asyncio
import json
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

_CHECKPOINT_DB = Path.home() / ".yumii" / "memory" / "checkpoints.db"

# Per-provider request budgets: free-tier Groq 413s over ~12k tokens (and tool
# results persist into history), so it gets tight caps; roomy providers get more.
_GROQ_MAX_TOOL_RESULT_CHARS = 3000
_GROQ_HISTORY_WINDOW = 12
_MAX_TOOL_RESULT_CHARS = 20000
_HISTORY_WINDOW = 40

# Bound tool runs so a stalled HTTP call can't hang the turn forever.
_TOOL_EXECUTION_TIMEOUT_SEC = 90.0


def _request_budgets() -> tuple[int, int]:
    """Return ``(max_tool_result_chars, history_window)`` for the active provider."""
    if settings.llm_provider.lower() == "groq":
        return _GROQ_MAX_TOOL_RESULT_CHARS, _GROQ_HISTORY_WINDOW
    return _MAX_TOOL_RESULT_CHARS, _HISTORY_WINDOW


def _truncate_tool_results(result: Any, max_chars: int | None = None) -> Any:
    """Cap oversized ToolMessage contents before they enter the state."""
    if max_chars is None:
        max_chars, _ = _request_budgets()
    messages = result.get("messages", []) if isinstance(result, dict) else []
    for m in messages:
        if not isinstance(m, ToolMessage):
            continue
        content = m.content if isinstance(m.content, str) else str(m.content)
        if len(content) > max_chars:
            m.content = (
                content[:max_chars]
                + "\n... [result truncated — too long for the conversation context]"
            )
            log.info(
                "tool_result_truncated", tool=m.name, original_chars=len(content)
            )
    return result


def _repair_dangling_tool_calls(messages: list) -> list:
    """Answer unanswered tool_calls with a synthetic ToolMessage.

    An interrupted turn leaves a tool_call with no result; providers require
    every tool_call_id answered, or every later request in the session errors.
    """
    answered = {
        m.tool_call_id for m in messages if isinstance(m, ToolMessage)
    }
    out: list = []
    for m in messages:
        out.append(m)
        if not isinstance(m, AIMessage):
            continue
        for call in getattr(m, "tool_calls", None) or []:
            call_id = call.get("id", "")
            if call_id and call_id not in answered:
                log.info("dangling_tool_call_repaired", tool=call.get("name", ""))
                out.append(
                    ToolMessage(
                        content="[interrupted — this tool call produced no result]",
                        tool_call_id=call_id,
                        name=call.get("name", ""),
                    )
                )
    return out


def _window_history(history: list, window: int | None = None) -> list:
    """Recent history slice for the request; never starts on an orphaned ToolMessage, repairs dangling calls."""
    if window is None:
        _, window = _request_budgets()
    windowed = history[-window:]
    while windowed and isinstance(windowed[0], ToolMessage):
        windowed = windowed[1:]
    return _repair_dangling_tool_calls(windowed)


def _build_state_class() -> type:
    """Combine MessagesState (the ``messages`` reducer) with Yumii's own state fields."""

    class YumiiMainState(MessagesState, total=False):
        """Yumii's full graph state. Inherits ``messages`` from MessagesState."""

        input: str
        turn_id: str
        response: str
        # turn_id that produced ``response`` — lets the engine tell a fresh reply from a stale one.
        response_turn_id: str
        expression: str
        motion: str
        session_id: str
        session_name: str
        user_facts: list[str]
        session_context: str

    return YumiiMainState


YumiiState: type = _build_state_class()


async def agent_node(state: dict[str, Any]) -> dict[str, Any]:
    """Run the tool-bound LLM; route to tools or END, running the synthesizer on the final turn."""
    user_input: str = state.get("input", "")
    history: list = state.get("messages", []) or []
    session_id: str = state.get("session_id", "")
    session_name: str = state.get("session_name", "")
    facts: list[str] = state.get("user_facts", []) or []
    session_context: str = state.get("session_context", "") or ""

    log.debug("agent_node_start", text=user_input)

    is_switch, new_personality = check_personality_switch(user_input)
    if is_switch:
        from yumii.core.global_config import update_global_config

        update_global_config("PERSONALITY", new_personality)
        user_input = (
            f"I want you to become {new_personality}. "
            "Acknowledge this personality switch warmly in your new style."
        )

    facts_text = "\n".join(f"  - {f}" for f in facts)
    bound = get_agent_llm(
        session_id=session_id,
        session_name=session_name,
        user_facts=facts_text or None,
        session_context=session_context or None,
    )

    # No per-turn time message — it would break provider prefix caching every
    # minute; the date lives at the tail of the system prompt instead.

    # Stable HumanMessage ID within a turn (dedupe re-adds) but unique across turns.
    turn_id: str = state.get("turn_id") or f"{session_id}_{hash(user_input)}"
    human_id = f"hum_{turn_id}"
    new_human = HumanMessage(content=user_input, id=human_id)
    messages: list = _window_history(list(history)) + [new_human]

    # Groq/Llama sometimes 400 with tool_use_failed — retry once, then apologize instead of crashing.
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

    if not getattr(response, "tool_calls", None):
        yumii_resp = synthesize(response.content or "")
        if not response.id:
            response = AIMessage(
                content=response.content,
                id=f"ai_{uuid.uuid4().hex}",
            )
        return {
            "messages": [new_human, response],
            "response": yumii_resp.response_text,
            "response_turn_id": turn_id,
            "expression": yumii_resp.expression,
            "motion": yumii_resp.motion,
        }

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
# Gated tools node — HITL confirmation
# ----------------------------------------------------------------------


def _tool_needs_confirmation(tool_name: str) -> bool:
    """Whether a tool needs confirmation under settings.hitl_mode (never / external / always)."""
    mode = (settings.hitl_mode or "external").lower()
    if mode == "never":
        return False
    if mode == "always":
        return True
    # "external" (and any unknown value — fail safe).
    return tool_name in set(tools_requiring_confirmation())


def _build_gated_tools_node(tools: list) -> Any:
    """Wrap ToolNode with a HITL gate: gated calls pause for the engine's confirmation hook."""
    inner = ToolNode(tools)

    async def run_tools(state: dict[str, Any], calls: list[dict]) -> dict[str, Any]:
        """Dispatch to the inner ToolNode with a hard timeout (errored ToolMessages on timeout)."""
        try:
            result = await asyncio.wait_for(
                inner.ainvoke(state), timeout=_TOOL_EXECUTION_TIMEOUT_SEC
            )
        except asyncio.TimeoutError:
            log.error(
                "tool_execution_timeout",
                tools=[c.get("name", "") for c in calls],
                timeout_sec=_TOOL_EXECUTION_TIMEOUT_SEC,
            )
            return {
                "messages": [
                    ToolMessage(
                        content=(
                            f"Tool call timed out after "
                            f"{int(_TOOL_EXECUTION_TIMEOUT_SEC)} seconds — no result."
                        ),
                        tool_call_id=c.get("id", ""),
                        name=c.get("name", ""),
                    )
                    for c in calls
                ]
            }
        return _truncate_tool_results(result)

    async def gated_tools_node(state: dict[str, Any]) -> dict[str, Any]:
        messages = list(state.get("messages") or [])
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
        seen_calls: set[tuple[str, str]] = set()

        for call in last_ai.tool_calls:
            name = call.get("name", "")
            args = call.get("args", {}) or {}
            call_id = call.get("id", "")

            # Drop duplicate calls (some models repeat one) — would fire a send N times / stack N popups.
            call_key = (name, json.dumps(args, sort_keys=True, default=str))
            if call_key in seen_calls:
                log.info("duplicate_tool_call_dropped", tool=name)
                denied_messages.append(
                    ToolMessage(
                        content=(
                            "Duplicate call skipped — this exact tool call "
                            "already ran in this step; use its result."
                        ),
                        tool_call_id=call_id,
                        name=name,
                    )
                )
                continue
            seen_calls.add(call_key)

            if not _tool_needs_confirmation(name):
                approved_calls.append(call)
                continue

            # Gated — ask the engine's hook.
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
            return await run_tools(state, list(last_ai.tool_calls))

        if not approved_calls:
            return {"messages": denied_messages}

        # Mixed: run approved calls, then append denials (every tool_call_id must be answered).
        trimmed_ai = AIMessage(
            content=last_ai.content,
            tool_calls=approved_calls,
            id=last_ai.id,
        )
        sub_state = {**state, "messages": messages[:-1] + [trimmed_ai]}
        inner_result = await run_tools(sub_state, approved_calls)
        inner_messages = (
            inner_result.get("messages", [])
            if isinstance(inner_result, dict)
            else []
        )
        return {"messages": list(inner_messages) + denied_messages}

    return gated_tools_node


# The engine injects its HITL hook here via set_confirmation_hook (avoids importing the engine).
_gated_tools_hook: dict[str, Any] = {"fn": None}


def set_confirmation_hook(fn) -> None:
    """Register the engine's HITL confirmation hook (awaited; returns approved bool; None clears)."""
    _gated_tools_hook["fn"] = fn


async def build_graph(checkpointer: AsyncSqliteSaver | None = None) -> Any:
    """Build the compiled LangGraph (AsyncSqliteSaver checkpoints; HITL-gated tools node)."""
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

    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", _build_gated_tools_node(tools))

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
