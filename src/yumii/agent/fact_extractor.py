"""Fact extraction engine for Yumii's long-term memory.

Uses a cheap LLM to analyse a short conversation snippet and extract atomic
facts about the user.  Returns structured JSON so downstream code can store
them directly in :class:`~yumii.core.memory_manager.MemoryManager`.
"""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from yumii.core.config import settings
from yumii.core.logging import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# System prompt for the extraction LLM
# ---------------------------------------------------------------------------

_EXTRACTION_SYSTEM_PROMPT = """\
You are a memory extraction engine. Your job is to analyse the conversation below and extract only new, concrete facts about the USER.

Rules:
- Extract facts the user reveals about themselves (preferences, identity, habits, goals, relationships).
- DO NOT extract facts about the assistant or the conversation itself.
- DO NOT extract obvious, trivial, or generic statements (e.g. "user is talking to an AI", "user asked a question").
- Each fact must be a single, atomic statement.
- Assign a confidence score 0.0–1.0 based on how explicitly the user stated the fact.
- If no new facts are present, return an empty facts array.

Categories (choose exactly one per fact):
- preference — things the user likes/dislikes
- identity — who the user is, their name, where they live, what they do
- habit — routines, daily patterns
- relationship — people the user knows, family, friends
- goal — things the user wants to achieve
- general — anything that doesn't fit the above

Return ONLY valid JSON in this exact format (no markdown, no extra text):
{"facts":[{"fact":"...","category":"...","confidence":0.0}]}
"""

# ---------------------------------------------------------------------------
# LLM helpers
# ---------------------------------------------------------------------------


def _get_extractor_llm() -> Any:
    """Return a cheap LLM instance suitable for fact extraction.

    Uses the configured provider but picks a cheaper/faster model variant so
    the cost of one extra call per conversation turn is negligible.
    """
    provider = settings.llm_provider.lower()

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.0,
            api_key=settings.openai_api_key,
        )

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model="claude-3-5-sonnet-latest",
            temperature=0.0,
            api_key=settings.anthropic_api_key,
        )

    # Default — Groq (cheapest, fastest)
    from langchain_groq import ChatGroq

    return ChatGroq(
        model="llama-3.1-8b-instant",
        temperature=0.0,
        api_key=settings.groq_api_key,
    )


def _format_messages_for_prompt(messages: list[dict[str, str]]) -> str:
    """Turn a list of {role, content} dicts into a plain-text conversation log."""
    lines: list[str] = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        label = "User" if role == "user" else "Assistant"
        lines.append(f"[{label}]: {content}")
    return "\n".join(lines)


def _parse_extraction_json(raw: str) -> list[dict[str, Any]]:
    """Robustly parse the LLM's JSON response, handling markdown fences."""
    text = raw.strip()

    # Try to find JSON inside markdown fences
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        text = match.group(1).strip()

    # Some models wrap the JSON in extra prose — try the first { ... } block
    if not text.startswith("{"):
        brace_match = re.search(r"(\{.*\})", text, re.DOTALL)
        if brace_match:
            text = brace_match.group(1).strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        log.warning("extraction_json_parse_failed", raw_preview=text[:200], error=str(exc))
        return []

    if isinstance(parsed, dict):
        return parsed.get("facts", [])
    if isinstance(parsed, list):
        return parsed
    return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def extract_facts(
    messages: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """Analyse *messages* and return a list of extracted fact dicts.

    Each fact dict contains ``fact``, ``category``, and ``confidence`` keys.
    Returns an empty list when no new facts are found or parsing fails.
    """
    if not messages:
        return []

    conversation_text = _format_messages_for_prompt(messages)
    llm = _get_extractor_llm()

    prompt_messages = [
        SystemMessage(content=_EXTRACTION_SYSTEM_PROMPT),
        HumanMessage(content=conversation_text),
    ]

    try:
        response = await llm.ainvoke(prompt_messages)
    except Exception as exc:
        log.error("extraction_llm_failed", error=str(exc))
        return []

    raw_text = getattr(response, "content", str(response))
    facts = _parse_extraction_json(raw_text)

    # Validate and sanitize
    valid_facts: list[dict[str, Any]] = []
    for f in facts:
        if not isinstance(f, dict):
            continue
        fact_text = str(f.get("fact", "")).strip()
        if not fact_text:
            continue
        category = str(f.get("category", "general")).lower().strip()
        if category not in {
            "preference",
            "identity",
            "habit",
            "relationship",
            "goal",
            "general",
        }:
            category = "general"
        confidence = float(f.get("confidence", 1.0))
        confidence = max(0.0, min(1.0, confidence))
        valid_facts.append(
            {
                "fact": fact_text,
                "category": category,
                "confidence": confidence,
            }
        )

    log.info("facts_extracted", count=len(valid_facts), raw_count=len(facts))
    return valid_facts
