"""LLM (Large Language Model) initialization for Yumii.

This module owns two things:

* The :class:`YumiiResponse` Pydantic model — the structured shape
  the engine reads from the graph output. PR 3's heuristic
  :func:`yumii.agent.synthesizer.synthesize` produces it.
* A factory :func:`get_agent_llm` that returns the active LLM
  **with the registry's tools bound** via ``bind_tools``. The graph
  uses this directly (no more ``create_agent`` wrapper) so we get
  full control over the message stream and ``interrupt_before`` is
  meaningful.

Per-personality and per-fact system prompts are computed and cached
here. Switching personalities (a slash command) simply invalidates
the relevant cache key.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from yumii.core.config import settings
from yumii.tools.registry import bind_to_llm

log = logging.getLogger(__name__)


class YumiiResponse(BaseModel):
    """Yumii's structured reply.

    Always populate all three fields. ``expression`` and ``motion`` MUST
    be chosen from the lists defined in the active personality prompt.

    The agent (LLM with ``bind_tools``) does NOT emit this shape
    directly — it emits plain text. The synthesizer runs after the
    final LLM turn and produces this object.
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


# ----------------------------------------------------------------------
# Base LLM
# ----------------------------------------------------------------------

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


# ----------------------------------------------------------------------
# System prompt + tool-bound LLM
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class BoundLLM:
    """A tool-bound LLM plus the system prompt the agent must prepend.

    Bundling both in one cache entry lets the agent node do:

        prompt_msg = SystemMessage(content=bound.system_prompt)
        response = await bound.llm.ainvoke([prompt_msg, *messages])

    without having to re-derive the personality / facts hash on every
    turn.
    """

    llm: Any  # BaseChatModel with tools bound
    system_prompt: str
    personality: str

    async def ainvoke(self, messages: list) -> Any:
        """Convenience wrapper that prepends the system prompt."""
        from langchain_core.messages import SystemMessage

        return await self.llm.ainvoke([SystemMessage(content=self.system_prompt), *messages])


# The tool-bound LLM is built once and shared: tool schemas don't
# change after startup, and binding fresh per turn would defeat the
# point. The system prompt, by contrast, is rebuilt every call — it's
# a cheap string concat, and it must reflect facts/date changes.
_bound_llm: Any | None = None


def _get_bound_llm() -> Any:
    global _bound_llm
    if _bound_llm is None:
        _bound_llm = bind_to_llm(base_llm)
    return _bound_llm


def _build_system_prompt(personality_name: str, user_facts: str | None = None) -> str:
    """Assemble the system prompt in provider-cache-friendly order.

    Prefix (KV) caching on Groq/OpenAI/Anthropic matches the request
    byte-for-byte from the start and dies at the first difference, so
    the layout is strictly ordered by mutation frequency:

      1. core + personality  — static forever            → always cached
      2. today's date        — changes once per day
      3. user facts          — changes when a fact lands
      (conversation history and the new message follow, append-only)

    The date deliberately has no clock time (that would break the
    cache every minute — the old layout's mistake); the agent has the
    ``get_current_time`` tool for precise time.
    """
    import datetime

    # Import here to avoid a circular import at module load time
    from yumii.agent.personality_manager import personality_manager

    core = personality_manager.load_core_prompt()
    persona = personality_manager.load_personality(personality_name)
    prompt = f"{core}\n\n{persona}"
    prompt += f"\n\nToday is {datetime.datetime.now().strftime('%A, %B %d, %Y')}."
    if user_facts:
        prompt += f"\n\nWhat you know about the user:\n{user_facts}"
    return prompt


def get_agent_llm(
    session_id: str,
    session_name: str = "",
    user_facts: str | None = None,
) -> BoundLLM:
    """Return a :class:`BoundLLM` for the current personality + fact set.

    The returned object exposes ``ainvoke(messages)`` which prepends
    the freshly-assembled system prompt. The graph wraps it in an
    agent node.

    Args:
        session_id: The active session ID. Currently unused but kept
            on the signature for future per-session prompt tuning.
        session_name: Human-readable session label. Currently unused.
        user_facts: Pre-formatted facts string to append to the
            system prompt. ``None`` or empty means no facts.

    Returns:
        A :class:`BoundLLM` carrying the shared tool-bound LLM and the
        system prompt the agent must inject.
    """
    from yumii.agent.personality_manager import personality_manager

    personality = personality_manager.get_current_personality()
    return BoundLLM(
        llm=_get_bound_llm(),
        system_prompt=_build_system_prompt(personality, user_facts),
        personality=personality,
    )


def clear_llm_cache() -> None:
    """Reset the shared tool binding (used after registry changes in tests)."""
    global _bound_llm
    _bound_llm = None


# Backwards-compat alias for code/tests that referenced the old name.
def clear_agent_cache() -> None:
    """Deprecated alias for :func:`clear_llm_cache`."""
    clear_llm_cache()


__all__ = [
    "YumiiResponse",
    "BoundLLM",
    "base_llm",
    "get_agent_llm",
    "clear_llm_cache",
    "clear_agent_cache",
]
