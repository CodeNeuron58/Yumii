"""Shared type definitions for the Yumii codebase."""

from typing import Annotated, Literal, TypedDict

from langgraph.graph import add_messages

# --- AI Reasoning Types ---


class MainState(TypedDict):
    """The shared state for Yumii's LangGraph reasoning engine."""

    messages: Annotated[list, add_messages]  # Conversation history for LLM
    input: str
    response: str
    expression: str
    motion: str
    session_id: str
    session_name: str  # Human-readable session label
    user_facts: list[str]  # Injected long-term memory facts


# --- Personality Types ---

PERSONALITY_TYPE = Literal[
    "caring", "tsundere", "genki", "kuudere", "yandere", "dandere"
]
