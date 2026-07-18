"""Agent-written long-term memory (manage_memory): add/replace/remove facts on the user's word.

WRITE policy, ungated — it only touches the user's own local facts. Replace/remove
target a fact by a short unique substring, not an ID.
"""

from __future__ import annotations

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from yumii.core.logging import get_logger
from yumii.tools.policy import ToolCategory, ToolPolicy
from yumii.tools.registry import register

log = get_logger(__name__)

_VALID_CATEGORIES = {"preference", "identity", "habit", "relationship", "goal", "general"}


class ManageMemoryInput(BaseModel):
    """Input schema for :func:`manage_memory`."""

    action: str = Field(
        description="One of: 'add' (save a new fact), 'replace' (correct an existing fact), 'remove' (forget a fact)."
    )
    fact: str | None = Field(
        default=None,
        description=(
            "For add/replace: the fact to store, as one short atomic "
            "statement about the user, e.g. 'user's birthday is March 3rd'."
        ),
    )
    old_text: str | None = Field(
        default=None,
        description=(
            "For replace/remove: a short distinctive substring of the "
            "existing fact to target, e.g. 'birthday'. Must match exactly "
            "one stored fact."
        ),
    )
    category: str | None = Field(
        default=None,
        description=(
            "For add/replace, optional: preference, identity, habit, "
            "relationship, goal, or general."
        ),
    )


@tool("manage_memory", args_schema=ManageMemoryInput)
async def manage_memory(
    action: str,
    fact: str | None = None,
    old_text: str | None = None,
    category: str | None = None,
) -> str:
    """Save, correct, or forget a long-term fact about the user.

    Use when the user explicitly asks you to remember or forget
    something, corrects something you remembered wrong, or states an
    important durable fact (name, birthday, preference, goal). Facts are
    injected into your memory in every future conversation, so keep them
    short, atomic, and high-signal — skip trivia and anything temporary.
    Prefer 'replace' over adding a near-duplicate. Do this quietly: a
    brief natural acknowledgement, never a report about memory systems.
    """
    from yumii.core.memory_manager import memory_manager

    action = (action or "").lower().strip()
    fact = (fact or "").strip()
    old_text = (old_text or "").strip()
    cat = (category or "general").lower().strip()
    if cat not in _VALID_CATEGORIES:
        cat = "general"

    if action == "add":
        if not fact:
            return "Nothing to save — 'fact' is required for add."
        # Near-duplicate guard: point the model at replace instead.
        existing = await memory_manager.find_facts_matching(fact[:40])
        if any(fact.lower() in f.fact.lower() or f.fact.lower() in fact.lower() for f in existing):
            return (
                "A very similar fact is already stored. Use action='replace' "
                "with old_text if it needs updating."
            )
        await memory_manager.store_fact(fact, category=cat)
        log.info("memory_tool_add", fact_preview=fact[:60])
        return f"Saved: {fact}"

    if action == "replace":
        if not fact or not old_text:
            return "replace needs both 'old_text' (target) and 'fact' (new text)."
        result = await memory_manager.replace_fact_by_text(old_text, fact)
        if result == "replaced":
            log.info("memory_tool_replace", old=old_text[:40], fact_preview=fact[:60])
            return f"Updated: {fact}"
        return _miss_message(result, old_text)

    if action == "remove":
        if not old_text:
            return "remove needs 'old_text' identifying the fact to forget."
        result = await memory_manager.remove_fact_by_text(old_text)
        if result == "removed":
            log.info("memory_tool_remove", old=old_text[:40])
            return "Forgotten."
        return _miss_message(result, old_text)

    return f"Unknown action {action!r} — use add, replace, or remove."


def _miss_message(result: str, old_text: str) -> str:
    if result == "ambiguous":
        return (
            f"Several stored facts contain '{old_text}' — call again with a "
            "longer, more distinctive substring."
        )
    return (
        f"No stored fact contains '{old_text}'. If this is new information, "
        "use action='add' instead."
    )


# Local-only WRITE, ungated.
register(
    manage_memory,
    ToolPolicy(
        category=ToolCategory.WRITE,
        requires_confirmation=False,
    ),
)


__all__ = ["ManageMemoryInput", "manage_memory"]
