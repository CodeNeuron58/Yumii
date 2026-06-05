"""Reasoning graph definition for Yumii.

Defines the LangGraph workflow that orchestrates the LLM interaction loop
and maintains the conversational state using **persistent** SQLite checkpoints.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, StateGraph

from yumii.agent.nodes import chat_node
from yumii.core.types import MainState

from yumii.core.logging import get_logger

log = get_logger(__name__)

# LangGraph checkpoints live in their own SQLite file.
_CHECKPOINT_DB = Path.home() / ".yumii" / "memory" / "checkpoints.db"


async def build_graph(checkpointer: AsyncSqliteSaver | None = None) -> Any:
    """Build and return the compiled LangGraph for Yumii's reasoning engine.

    Uses :class:`AsyncSqliteSaver` so conversation history survives
    server restarts.  Each session gets its own ``thread_id`` checkpoint
    namespace automatically.
    """

    def think_node(state: MainState) -> dict:
        """Run the LLM ReAct loop and return a structured YumiiResponse."""
        log.debug("user_input", text=state["input"])
        result = chat_node(
            {
                "input": state["input"],
                "messages": state.get("messages", []),
                "session_id": state["session_id"],
                "session_name": state.get("session_name", ""),
                "user_facts": state.get("user_facts", []),
            }
        )
        return {
            "response": result["response"],
            "expression": result.get("expression") or "normal",
            "motion": result.get("motion") or "idle",
            "messages": result.get("messages", []),
        }

    log.info("langgraph_building")
    workflow = StateGraph(MainState)

    workflow.add_node("think", think_node)
    workflow.set_entry_point("think")
    workflow.add_edge("think", END)

    if checkpointer is None:
        _CHECKPOINT_DB.parent.mkdir(parents=True, exist_ok=True)
        async with AsyncSqliteSaver.from_conn_string(str(_CHECKPOINT_DB)) as saver:
            return workflow.compile(checkpointer=saver)
    return workflow.compile(checkpointer=checkpointer)
