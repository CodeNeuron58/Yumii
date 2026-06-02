"""
Individual reasoning nodes for Yumi's LangGraph.

Contains logic for processing user input, handling personality switches,
and invoking the LLM agent.
"""


from langchain_core.messages import AIMessage, HumanMessage

from yumi.agent.llm import get_agent
from yumi.agent.personality_manager import personality_manager
from yumi.core.types import MainState

from yumi.core.logging import get_logger
log = get_logger(__name__)


def check_personality_switch(user_input: str) -> tuple[bool, str | None]:
    """Check if the user input contains a request to switch personalities.

    Returns:
        A tuple of (True, new_personality) if a switch was requested, else (False, None).
    """
    lowered = user_input.lower().strip()
    for personality in personality_manager.list_personalities():
        if lowered in (
            f"switch to {personality}",
            f"be {personality}",
            f"become {personality}",
            personality,
        ):
            return True, personality
    return False, None


def chat_node(state: MainState) -> dict:
    """Execute the core reasoning node.

    Invokes the LLM agent and returns a structured response containing
    text, expression, and motion instructions.
    """
    user_input: str = state["input"]
    history: list = state.get("messages", [])

    is_switch, new_personality = check_personality_switch(user_input)
    if is_switch:
        from yumi.core.global_config import update_global_config

        update_global_config("PERSONALITY", new_personality)
        user_input = (
            f"I want you to become {new_personality}. "
            "Acknowledge this personality switch warmly in your new style."
        )

    current_personality = personality_manager.get_current_personality()
    agent = get_agent(current_personality)

    new_human_message = HumanMessage(content=user_input)
    input_messages = history + [new_human_message]

    result = agent.invoke({"messages": input_messages})

    structured_response = result.get("structured_response")
    if structured_response is None:
        log.warning("llm_no_structured_response")

        class FallbackResponse:
            response_text = (
                "I'm having a little trouble right now. Could you say that again?"
            )
            expression = "sad"
            motion = "idle"

        structured_response = FallbackResponse()

    messages_to_append = [
        new_human_message,
        AIMessage(content=structured_response.response_text),
    ]

    return {
        "response": structured_response.response_text,
        "expression": getattr(structured_response, "expression", "normal"),
        "motion": getattr(structured_response, "motion", "idle"),
        "messages": messages_to_append,
    }
