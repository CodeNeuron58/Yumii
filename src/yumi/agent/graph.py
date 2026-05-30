from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import InMemorySaver

from yumi.agent.nodes import chat_node
from yumi.core.types import MainState

def build_graph():
    """
    Build and return the compiled LangGraph for Yumi's reasoning engine.
    This graph handles the LLM ReAct loop and state memory.
    """

    def think_node(state: MainState) -> dict:
        """Run the LLM ReAct loop and return a structured YumiResponse."""
        print(f"User: {state['input']}")
        result = chat_node({
            "input": state["input"],
            "messages": state.get("messages", []),
            "session_id": state["session_id"]
        })
        return {
            "response": result["response"],
            "expression": result.get("expression") or "normal",
            "motion": result.get("motion") or "idle",
            "messages": result.get("messages", [])
        }

    print("Building LangGraph...")
    workflow = StateGraph(MainState)

    workflow.add_node("think", think_node)
    workflow.set_entry_point("think")
    workflow.add_edge("think", END)

    saver = InMemorySaver()
    return workflow.compile(checkpointer=saver)
