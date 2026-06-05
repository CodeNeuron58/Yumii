"""LLM (Large Language Model) agent initialization and caching."""

from langchain.agents import create_agent
from langchain_anthropic import ChatAnthropic
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from yumii.core.config import settings
from yumii.tools import tools


class YumiiResponse(BaseModel):
    """Yumii's structured reply.

    Always populate all three fields.  expression and motion MUST be chosen
    from the lists defined in the active personality prompt.
    """

    response_text: str = Field(
        description="The conversational, concise text Yumii will speak out loud."
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
    base_llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0.7,
        api_key=settings.groq_api_key,
    )

# Short tool-ordering hint appended to every personality prompt.
# Groq/Llama can sometimes hallucinate <function=...> tags instead of proper tool calls.
# We explicitly forbid this and emphasize the structured response.
_TOOL_HINT = (
    "\n\nIMPORTANT: To respond to the user, you MUST call the `YumiiResponse` tool. "
    "\nDo NOT wrap your response in <function> tags or use any other format. "
    "\nKeep your spoken response text short and punchy: UNDER 3 sentences and strictly LESS THAN 400 characters."
)

# Lazy cache: (personality_name, facts_hash) → compiled create_agent instance
_agent_cache: dict[tuple[str, int], object] = {}


def _build_system_prompt(personality_name: str, user_facts: str | None = None) -> str:
    """Return the full system prompt for a personality (prompt file + tool hint + facts)."""
    # Import here to avoid a circular import at module load time
    from yumii.agent.personality_manager import personality_manager

    base = personality_manager.load_personality(personality_name)
    prompt = base + _TOOL_HINT
    if user_facts:
        prompt += f"\n\n{user_facts}"
    return prompt


def get_agent(personality: str, user_facts: str | None = None) -> object:
    """Return the create_agent instance for *personality*, building it on first use.

    The agent is cached so subsequent calls with the same personality and
    fact set are free.  Personality switching simply calls get_agent with
    the new name; long-term memory updates call it with new facts.
    """
    cache_key = (personality, hash(user_facts or ""))
    if cache_key not in _agent_cache:
        system_prompt = _build_system_prompt(personality, user_facts)
        _agent_cache[cache_key] = create_agent(
            model=base_llm,
            tools=[],
            response_format=YumiiResponse,
            system_prompt=system_prompt,
        )
    return _agent_cache[cache_key]


def clear_agent_cache() -> None:
    """Invalidate all cached agents (e.g. after a system-prompt change)."""
    _agent_cache.clear()
