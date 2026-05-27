from langchain_core.messages import HumanMessage, AIMessage
from yumi.agent.llm import get_agent
from yumi.agent.personality_manager import personality_manager


# ---------------------------------------------------------------------------
# Personality switch detection
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Chat node
# ---------------------------------------------------------------------------

def chat_node(state: dict) -> dict:
    """
    Core reasoning node — invokes the LLM agent and returns structured output.

    What changed vs the old version
    ────────────────────────────────
    Before:
      • Manually built [SystemMessage, ...history, HumanMessage] every turn.
      • Injected a 60-token CRITICAL INSTRUCTION to prevent tool/schema conflicts.
      • Called a single global agent instance regardless of active personality.

    Now:
      • Passes only (history + new HumanMessage) to the agent.
      • The system prompt (personality + tool hint) is baked into the agent via
        create_agent(system_prompt=...) in llm.py and injected by the framework
        inside the ReAct loop — at the correct position, before every LLM call.
      • Selects the right cached agent for the current personality.
      • The CRITICAL INSTRUCTION is gone — replaced by a one-line _TOOL_HINT
        in llm.py, appended once at agent-build time.

    History strategy (unchanged — this is the correct pattern)
    ──────────────────────────────────────────────────────────
    We discard the agent's internal tool-call trace (ToolMessages, intermediate
    AIMessages with tool_calls) and store only a clean HumanMessage + plain
    AIMessage in state.  This prevents ToolMessage confusion on subsequent turns
    while keeping history readable for the LLM.
    """
    user_input: str = state["input"]
    history: list = state.get("messages", [])

    # 1. Personality switch detection
    is_switch, new_personality = check_personality_switch(user_input)
    if is_switch:
        from yumi.core.global_config import update_global_config
        update_global_config("PERSONALITY", new_personality)
        # Rewrite input so the LLM acknowledges the switch in its new style
        user_input = (
            f"I want you to become {new_personality}. "
            "Acknowledge this personality switch warmly in your new style."
        )

    # 2. Resolve the correct agent for the current personality.
    #    get_agent() reads personality from config.json and returns a cached
    #    create_agent instance — no agent rebuild unless personality changed.
    current_personality = personality_manager.get_current_personality()
    agent = get_agent(current_personality)

    # 3. Build the message list — system prompt is handled by the agent itself.
    new_human_message = HumanMessage(content=user_input)
    input_messages = history + [new_human_message]

    # 4. Run the ReAct loop
    result = agent.invoke({"messages": input_messages})

    # 5. Extract structured response
    structured_response = result.get("structured_response")
    if structured_response is None:
        # LLM did not call the output schema — likely a tool-loop timeout.
        print("WARNING: structured_response was None — LLM did not produce YumiResponse.")
        class _Fallback:
            response_text = "I'm having a little trouble right now. Could you say that again?"
            expression = "sad"
            motion = "idle"
        structured_response = _Fallback()

    # 6. Return clean messages to state (see history strategy in docstring)
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
