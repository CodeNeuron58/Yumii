"""LLM setup: the YumiiResponse model + a get_agent_llm factory (tools bound via bind_tools).

The system prompt is assembled fresh each turn; only the tool-bound LLM is cached.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

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

# Legacy fallbacks, used only when no catalog selection exists for a provider.
_DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
_DEFAULT_ANTHROPIC_MODEL = "claude-3-5-haiku-latest"


def build_ollama_llm(model: str, temperature: float = 0.7) -> Any:
    """Build a ChatOllama for Ollama Cloud (Bearer key via client_kwargs) or a local base_url."""
    from langchain_ollama import ChatOllama

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


def _resolve_model(provider: str) -> str:
    """The model to speak with: catalog selection first, per-provider key, legacy default."""
    if settings.llm_model:
        return settings.llm_model
    from yumii.core.model_catalog import NEBIUS_DEFAULT_MODEL

    per_provider = {
        "nebius": NEBIUS_DEFAULT_MODEL,
        "openai": settings.openai_model or _DEFAULT_OPENAI_MODEL,
        "anthropic": settings.anthropic_model or _DEFAULT_ANTHROPIC_MODEL,
        "groq": settings.groq_model,
        "ollama": settings.ollama_model,
    }.get(provider)
    if per_provider:
        return per_provider
    raise ValueError(
        f"No model selected for provider '{provider}'. "
        "Pick one in Settings → Model picker."
    )


def _provider_api_key(provider: str) -> str | None:
    """API key for a provider: settings fields where they exist, env (auth.json) otherwise."""
    direct = {
        "openai": settings.openai_api_key,
        "anthropic": settings.anthropic_api_key,
        "groq": settings.groq_api_key,
        "ollama": settings.ollama_api_key,
    }.get(provider)
    if direct:
        return direct
    from yumii.core.model_catalog import key_for

    return key_for(provider)


def _build_base_llm(temperature: float = 0.7, model: str | None = None) -> Any:
    """Construct the configured provider's chat model, lazily (constructors validate keys).

    Provider wiring comes from the model catalog (provider id → LangChain
    client + key name + base URL); the model id comes from the catalog
    selection unless an explicit ``model`` is passed. Unknown provider
    strings keep the legacy Groq fallback.
    """
    from yumii.core.model_catalog import get_wiring

    provider = settings.llm_provider.lower()
    wiring = get_wiring(provider)
    if wiring is None:
        # Unknown provider string — legacy behavior: Groq with its configured model.
        from langchain_groq import ChatGroq

        return ChatGroq(
            model=model or settings.groq_model,
            temperature=temperature,
            api_key=settings.groq_api_key,
        )

    chosen = model or _resolve_model(wiring.id)

    if wiring.kind == "anthropic":
        from langchain_anthropic import ChatAnthropic

        api_key = _provider_api_key(wiring.id)
        if not api_key:
            raise ValueError(
                "Anthropic needs an API key — add it in Settings → Model picker."
            )
        return ChatAnthropic(model=chosen, temperature=temperature, api_key=api_key)

    if wiring.kind == "groq":
        from langchain_groq import ChatGroq

        api_key = _provider_api_key(wiring.id)
        if not api_key:
            raise ValueError("Groq needs an API key — add it in Settings → Model picker.")
        return ChatGroq(model=chosen, temperature=temperature, api_key=api_key)

    if wiring.kind == "ollama":
        return build_ollama_llm(chosen, temperature=temperature)

    # "openai" and every "openai-compatible" provider (Nebius, Google,
    # OpenRouter, DeepSeek, xAI, Together, Mistral) speak the OpenAI wire protocol.
    api_key = _provider_api_key(wiring.id)
    if not api_key and not wiring.key_optional:
        raise ValueError(
            f"{wiring.name} needs an API key — add it in Settings → Model picker."
        )
    from langchain_openai import ChatOpenAI

    kwargs: dict[str, Any] = {}
    if wiring.extra_body:
        kwargs["extra_body"] = dict(wiring.extra_body)
    return ChatOpenAI(
        model=chosen,
        temperature=temperature,
        api_key=api_key or "unused",
        base_url=wiring.base_url,
        **kwargs,
    )


def build_background_llm(temperature: float = 0.0) -> Any:
    """The provider's cheap tier for background jobs (memory review, summaries).

    Prefers the catalog's small/fast model so background work never runs —
    or pays for — the user's flagship chat model; falls back to the selected
    chat model when the catalog knows no cheap tier for the provider.
    Missing keys raise the same actionable errors as the agent's mind
    (callers catch and degrade with a warning).
    """
    from yumii.core.model_catalog import cheap_model_for

    cheap = cheap_model_for(settings.llm_provider)
    if cheap:
        return _build_base_llm(temperature=temperature, model=cheap)
    return _build_base_llm(temperature=temperature)


# ----------------------------------------------------------------------
# System prompt + tool-bound LLM
# ----------------------------------------------------------------------


# Re-stated AFTER the conversation history on every call. Long histories wear
# instructions down (persona adherence measurably drops within ~8 turns, and
# Nemotron 3 Super's thinking-off mode is weakest at multi-turn instruction
# following), and a 9-scenario baseline showed exactly these rules slipping.
# Sitting at the end, it never disturbs the cacheable prompt prefix.
VOICE_ANCHOR = (
    "Reminder from the system, not from them. It is {now}. First: if a tool is needed — a search, "
    "remembering or forgetting something, their email — call it now, before you say anything. "
    "Then speak out loud: usually one or two sentences, under twenty-five words, unless they "
    "asked for more; words only, no emojis, symbols, lists or stage directions; most replies end "
    "without a question, never two. Only say something was saved, sent or found if a tool did it "
    "in this turn. Stay in character."
)


@dataclass(frozen=True)
class BoundLLM:
    """A tool-bound LLM plus the system prompt the agent prepends (and the voice anchor it appends)."""

    llm: Any  # BaseChatModel with tools bound
    system_prompt: str
    personality: str
    voice_anchor: str | None = None

    async def ainvoke(self, messages: list) -> Any:
        """Prepend the system prompt; append the voice anchor after the history."""
        from langchain_core.messages import SystemMessage

        tail = [SystemMessage(content=self.voice_anchor)] if self.voice_anchor else []
        return await self.llm.ainvoke([SystemMessage(content=self.system_prompt), *messages, *tail])


# Tool-bound LLM built once (tool schemas are static); the system prompt is rebuilt per call.
_bound_llm: Any | None = None


def _get_bound_llm() -> Any:
    global _bound_llm
    if _bound_llm is None:
        _bound_llm = bind_to_llm(_build_base_llm())
    return _bound_llm


def _mind_line() -> str:
    """Name the model she thinks with, so "does my conversation leave my computer?" gets a true answer."""
    from yumii.core.model_catalog import get_model, get_wiring

    wiring = get_wiring(settings.llm_provider)
    if wiring is None:
        return ""
    try:
        model = _resolve_model(wiring.id)
    except ValueError:
        return ""
    name = (get_model(wiring.id, model) or {}).get("name") or model
    if model.lower().startswith("nvidia/") and "nvidia" not in name.lower():
        name = f"NVIDIA {name}"
    if wiring.kind == "ollama":
        base = (settings.ollama_base_url or "").lower()
        if "localhost" in base or "127.0.0.1" in base:
            return (
                f"Your mind right now is {name}, running entirely on this computer: "
                "your conversations and memories never need to leave it."
            )
    provider = wiring.name.split(" (")[0]
    return (
        f"Your mind right now is {name}, running in the cloud on {provider}: what the two of you "
        "say is sent there so you can think and reply, while your memories of them stay on this computer. "
        "You don't know what the provider keeps, so never promise anything about that."
    )


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
    mind = _mind_line()  # changes only when they switch models — still cache-friendly
    if mind:
        prompt += f"\n\n{mind}"
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

    from yumii.core.model_catalog import get_wiring

    personality = personality_manager.get_current_personality()
    wiring = get_wiring(settings.llm_provider)
    # Anthropic's API takes a system prompt only at the start — no trailing anchor there.
    anchored = wiring is None or wiring.kind != "anthropic"
    return BoundLLM(
        llm=_get_bound_llm(),
        system_prompt=_build_system_prompt(personality, user_facts, session_context),
        personality=personality,
        voice_anchor=voice_anchor() if anchored else None,
    )


def voice_anchor() -> str:
    """The per-turn anchor, carrying the clock time — after the history, so the cached
    prefix never changes. A model asked "what time is it?" without one guessed wrong
    (Nemotron missed the time tool on 1 in 4 tries and invented an hour)."""
    import datetime

    now = datetime.datetime.now().strftime("%I:%M %p on %A, %B %d").lstrip("0")
    return VOICE_ANCHOR.format(now=now)


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
    "build_background_llm",
    "clear_llm_cache",
    "clear_agent_cache",
]
