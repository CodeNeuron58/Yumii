"""Reasoning graph definition for Yumii.

Defines the LangGraph workflow that orchestrates the LLM interaction loop
and maintains the conversational state.
"""


from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, StateGraph

from yumii.agent.nodes import chat_node
from yumii.core.types import MainState

from yumii.core.logging import get_logger
log = get_logger(__name__)


def build_graph() -> Any:
    """Build and return the compiled LangGraph for Yumii's reasoning engine.

    This graph handles the LLM ReAct loop and state memory.
    """

    def think_node(state: MainState) -> dict:
        """Run the LLM ReAct loop and return a structured YumiiResponse."""
        log.debug("user_input", text=state["input"])
        result = chat_node(
            {
                "input": state["input"],
                "messages": state.get("messages", []),
                "session_id": state["session_id"],
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

    saver = InMemorySaver()
    return workflow.compile(checkpointer=saver)
