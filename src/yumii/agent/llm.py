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
# System prompt + per-personality/per-fact LLM binding
# ----------------------------------------------------------------------

# Tools-only hint appended to every personality prompt. The agent
# still has ``bind_tools``, so it can call get_current_time, etc.;
# the hint steers it to a conversational style.
_TOOL_HINT = (
    "\n\nYou have access to tools. Use them when the user asks for "
    "live information (e.g. current time, timezone lookups). For "
    "ordinary conversation, just respond directly.\n"
    "Keep your spoken response short and punchy: UNDER 3 sentences and "
    "strictly LESS THAN 400 characters."
)


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


# Lazy cache: (personality_name, facts_hash) -> BoundLLM.
# We cache the bound LLM because ``bind_tools`` is cheap but not free
# (it copies the tool schemas into the LLM's request format).
_llm_cache: dict[tuple[str, int], BoundLLM] = {}


def _build_system_prompt(personality_name: str, user_facts: str | None = None) -> str:
    """Return the full system prompt for a personality (prompt file + tool hint + facts)."""
    # Import here to avoid a circular import at module load time
    from yumii.agent.personality_manager import personality_manager

    base = personality_manager.load_personality(personality_name)
    prompt = base + _TOOL_HINT
    if user_facts:
        prompt += f"\n\nKnown facts about the user:\n{user_facts}"
    return prompt


def get_agent_llm(
    session_id: str,
    session_name: str = "",
    user_facts: str | None = None,
) -> BoundLLM:
    """Return a :class:`BoundLLM` for the current personality + fact set.

    The returned object exposes ``ainvoke(messages)`` which prepends
    the cached system prompt. The graph wraps it in an agent node.

    Args:
        session_id: The active session ID. Currently unused but kept
            on the signature for future per-session prompt tuning.
        session_name: Human-readable session label. Currently unused.
        user_facts: Pre-formatted facts string to append to the
            personality prompt. ``None`` or empty means no facts.

    Returns:
        A :class:`BoundLLM` carrying the tool-bound LLM and the
        system prompt the agent must inject.
    """
    from yumii.agent.personality_manager import personality_manager

    personality = personality_manager.get_current_personality()
    cache_key = (personality, hash(user_facts or ""))
    if cache_key in _llm_cache:
        return _llm_cache[cache_key]

    system_prompt = _build_system_prompt(personality, user_facts)
    bound = bind_to_llm(base_llm)

    entry = BoundLLM(
        llm=bound,
        system_prompt=system_prompt,
        personality=personality,
    )
    _llm_cache[cache_key] = entry
    return entry


def clear_llm_cache() -> None:
    """Invalidate all cached (personality, facts) bindings."""
    _llm_cache.clear()


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
