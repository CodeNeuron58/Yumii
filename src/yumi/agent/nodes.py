from langchain_core.messages import HumanMessage, AIMessage
from yumi.agent.llm import get_agent
from yumi.agent.personality_manager import personality_manager


def check_personality_switch(user_input: str) -> tuple[bool, str | None]:
    """Return (True, new_personality) if the user asked to switch, else (False, None)."""
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


def chat_node(state: dict) -> dict:
    """Core reasoning node — invokes the LLM agent and returns structured output.
    
    Discards internal tool-call traces and stores only clean Human/AIMessages 
    in state to maintain a readable history for subsequent turns.
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
        print("WARNING: structured_response was None — LLM did not produce YumiResponse.")
        class _Fallback:
            response_text = "I'm having a little trouble right now. Could you say that again?"
            expression = "sad"
            motion = "idle"
        structured_response = _Fallback()

    messages_to_append = [
        new_human_message,
        AIMessage(content=structured_response.response_text),
    ]

    return {
        "response": structured_response.response_text,
        "expression": getattr(structured_response, "expression", "normal"),
        "motion":     getattr(structured_response, "motion",     "idle"),
        "messages":   messages_to_append,
    }
