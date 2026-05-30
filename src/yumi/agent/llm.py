from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel, Field
from yumi.core.config import settings
from yumi.tools import tools
from langchain.agents import create_agent

class YumiResponse(BaseModel):
    """Yumi's structured reply.

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
    "\n\nIMPORTANT: To respond to the user, you MUST call the `YumiResponse` tool. "
    "\nDo NOT wrap your response in <function> tags or use any other format. "
    "\nKeep your spoken response text short and punchy: UNDER 3 sentences and strictly LESS THAN 400 characters. "
    "\nIf you need to use other tools (like getting the time), use them first before calling YumiResponse."
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
    """Return the create_agent instance for *personality*, building it on first use.

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
