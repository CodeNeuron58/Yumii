"""Per-turn helpers for Yumii's LangGraph.

Currently exposes the personality-switch detector used by
:mod:`yumii.agent.graph`'s ``agent_node``. The old ``chat_node`` has
been replaced by the graph's built-in ``agent`` + ``tools`` nodes
(PR 2 of the v1.0 redesign); see :func:`yumii.agent.graph.build_graph`.
"""

from __future__ import annotations

from yumii.agent.personality_manager import personality_manager
from yumii.core.logging import get_logger

log = get_logger(__name__)


def check_personality_switch(user_input: str) -> tuple[bool, str | None]:
    """Detect an in-band request to switch the active personality.

    The set of recognized phrasings is intentionally tiny — Yumii is
    a voice companion, and the user is expected to say things like
    "switch to tsundere" or just "tsundere". Anything more elaborate
    routes through normal LLM conversation.

    Returns:
        A tuple of ``(True, new_personality)`` if a switch was
        requested, else ``(False, None)``.
    """
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


__all__ = ["check_personality_switch"]
