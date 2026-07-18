"""LLM setup: the YumiiResponse model + a get_agent_llm factory (tools bound via bind_tools).

The system prompt is assembled fresh each turn; only the tool-bound LLM is cached.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from yumii.core.config import settings
from yumii.tools.registry import bind_to_llm

log = logging.getLogger(__name__)


class YumiiResponse(BaseModel):
    """Yumii's structured reply: response_text + expression + motion (produced by the synthesizer)."""

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


# ----------------------------------------------------------------------
# Base LLM
# ----------------------------------------------------------------------

def build_ollama_llm(model: str, temperature: float = 0.7) -> ChatOllama:
    """Build a ChatOllama for Ollama Cloud (Bearer key via client_kwargs) or a local base_url."""
    client_kwargs: dict = {}
    if settings.ollama_api_key:
        client_kwargs["headers"] = {
            "Authorization": f"Bearer {settings.ollama_api_key}"
        }
    return ChatOllama(
        model=model,
        temperature=temperature,
        base_url=settings.ollama_base_url,
        client_kwargs=client_kwargs,
    )


def _build_base_llm() -> Any:
    """Construct the configured provider's chat model, lazily (constructors validate keys)."""
    provider = settings.llm_provider.lower()
    if provider == "openai":
        return ChatOpenAI(
            model="gpt-4o",
            temperature=0.7,
            api_key=settings.openai_api_key,
        )
    if provider == "anthropic":
        return ChatAnthropic(
            model="claude-3-5-sonnet-latest",
            temperature=0.7,
            api_key=settings.anthropic_api_key,
        )
    if provider == "ollama":
        return build_ollama_llm(settings.ollama_model)
    return ChatGroq(
        model=settings.groq_model,
        temperature=0.7,
        api_key=settings.groq_api_key,
    )


# ----------------------------------------------------------------------
# System prompt + tool-bound LLM
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class BoundLLM:
    """A tool-bound LLM plus the system prompt the agent prepends."""

    llm: Any  # BaseChatModel with tools bound
    system_prompt: str
    personality: str

    async def ainvoke(self, messages: list) -> Any:
        """Convenience wrapper that prepends the system prompt."""
        from langchain_core.messages import SystemMessage

        return await self.llm.ainvoke([SystemMessage(content=self.system_prompt), *messages])


# Tool-bound LLM built once (tool schemas are static); the system prompt is rebuilt per call.
_bound_llm: Any | None = None


def _get_bound_llm() -> Any:
    global _bound_llm
    if _bound_llm is None:
        _bound_llm = bind_to_llm(_build_base_llm())
    return _bound_llm


def _build_system_prompt(
    personality_name: str,
    user_facts: str | None = None,
    session_context: str | None = None,
) -> str:
    """Assemble the system prompt ordered by mutation frequency (static → date → context → facts).

    Prefix caching dies at the first byte difference, so order matters; the
    date has no clock time (that would break the cache every minute).
    """
    import datetime

    # Imported here to avoid a circular import at module load time.
    from yumii.agent.personality_manager import personality_manager

    core = personality_manager.load_core_prompt()
    persona = personality_manager.load_personality(personality_name)
    prompt = f"{core}\n\n{persona}"
    prompt += f"\n\nToday is {datetime.datetime.now().strftime('%A, %B %d, %Y')}."
    if session_context:
        prompt += f"\n\n{session_context}"
    if user_facts:
        prompt += f"\n\nWhat you know about the user:\n{user_facts}"
    return prompt


def get_agent_llm(
    session_id: str,
    session_name: str = "",
    user_facts: str | None = None,
    session_context: str | None = None,
) -> BoundLLM:
    """Return a BoundLLM for the current personality + facts (its ainvoke prepends the prompt).

    ``session_id`` / ``session_name`` are currently unused (kept for future tuning).
    """
    from yumii.agent.personality_manager import personality_manager

    personality = personality_manager.get_current_personality()
    return BoundLLM(
        llm=_get_bound_llm(),
        system_prompt=_build_system_prompt(personality, user_facts, session_context),
        personality=personality,
    )


def clear_llm_cache() -> None:
    """Reset the shared tool binding (used after registry changes in tests)."""
    global _bound_llm
    _bound_llm = None


def clear_agent_cache() -> None:
    """Deprecated alias for :func:`clear_llm_cache`."""
    clear_llm_cache()


__all__ = [
    "YumiiResponse",
    "BoundLLM",
    "get_agent_llm",
    "clear_llm_cache",
    "clear_agent_cache",
]
