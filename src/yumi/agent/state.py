from typing import TypedDict, Annotated
from langgraph.graph import add_messages

class MainState(TypedDict):
    messages: Annotated[list, add_messages]  # Conversation history for LLM
    input: str
    response: str
    expression: str
    motion: str
    session_id: str
