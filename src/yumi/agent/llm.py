from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel, Field
from yumi.core.config import settings
from yumi.tools import tools
from langchain.agents import create_agent


# ---------------------------------------------------------------------------
# Structured response schema
# ---------------------------------------------------------------------------

class YumiResponse(BaseModel):
    """
    Yumi's structured reply.

    Always populate all three fields.  expression and motion MUST be chosen
    from the lists defined in the active personality prompt.
    """

    response_text: str = Field(
        description="The conversational, concise text Yumi will speak out loud."
    )
    expression: str = Field(
        description=(
            "One facial expression label from: "
            "smile, angry, sad, surprise, scared, shy, normal"
        )
    )
    motion: str = Field(
        description=(
            "One body motion label from: "
            "nod, shakehead, tilthead, fidget, forward, lookaway, greeting, idle"
        )
    )


# ---------------------------------------------------------------------------
# Base LLM — selected from config, initialised once
# ---------------------------------------------------------------------------

provider = settings.llm_provider.lower()

if provider == "openai":
    base_llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0.7,
        api_key=settings.openai_api_key,
    )
elif provider == "anthropic":
    base_llm = ChatAnthropic(
        model="claude-3-5-sonnet-latest",
        temperature=0.7,
        api_key=settings.anthropic_api_key,
    )
else:
    # Default: Groq
    base_llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0.7,
        api_key=settings.groq_api_key,
    )


# ---------------------------------------------------------------------------
# Agent factory — one agent per personality, cached
# ---------------------------------------------------------------------------
# Why per-personality agents instead of per-turn system prompt injection?
#
# Previously nodes.py manually rebuilt [SystemMessage, ...history, HumanMessage]
# on every call and passed it to a single global agent.  Problems with that:
#   1. The system prompt was injected OUTSIDE the agent's ReAct loop, so the
#      LLM never saw its own tool-call traces paired with the correct persona.
#   2. The CRITICAL INSTRUCTION workaround was needed because structured output
#      competed with real tools inside a single turn.
#   3. The agent's internal tool traces were thrown away and replaced with a
#      hand-built AIMessage — correct for history, but done for the wrong reason.
#
# With create_agent(system_prompt=...) the framework injects the system message
# INSIDE the agent's loop — before every LLM call — at the correct position.
# Personality switching = swap the cached agent instance, not rebuild messages.
# ---------------------------------------------------------------------------

# Short tool-ordering hint appended to every personality prompt.
# Groq/Llama has no native structured-output support and falls back to a
# tool-calling strategy, which can make it call the output schema tool before
# finishing real tool work.  This one-liner prevents that.
#
# ⚠️  Do NOT mention any tool name here by text.
#     Groq/Llama pattern-matches tool names in the system prompt and can
#     hallucinate malformed tool calls (e.g. ',get_current_time') that fail
#     with a 400 validation error from the API.
_TOOL_HINT = (
    "\n\nWhen you need information from a tool, call that tool first "
    "and wait for its result before generating your final YumiResponse."
)

# Lazy cache: personality name → compiled create_agent instance
_agent_cache: dict[str, object] = {}


def _build_system_prompt(personality_name: str) -> str:
    """Return the full system prompt for a personality (prompt file + tool hint)."""
    # Import here to avoid a circular import at module load time
    from yumi.agent.personality_manager import personality_manager
    base = personality_manager.load_personality(personality_name)
    return base + _TOOL_HINT


def get_agent(personality: str) -> object:
    """
    Return the create_agent instance for *personality*, building it on first use.

    The agent is cached so subsequent calls with the same personality are free.
    Personality switching (nodes.py) simply calls get_agent with the new name,
    which either hits the cache or builds a new instance once.
    """
    if personality not in _agent_cache:
        system_prompt = _build_system_prompt(personality)
        _agent_cache[personality] = create_agent(
            model=base_llm,
            tools=tools,
            response_format=YumiResponse,
            system_prompt=system_prompt,
        )
    return _agent_cache[personality]


def clear_agent_cache() -> None:
    """Invalidate all cached agents (e.g. after a system-prompt change)."""
    _agent_cache.clear()
