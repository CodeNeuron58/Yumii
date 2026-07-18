"""Per-turn LangGraph helpers — currently the personality-switch detector."""

from __future__ import annotations

import re

from yumii.agent.personality_manager import personality_manager
from yumii.core.logging import get_logger

log = get_logger(__name__)


def check_personality_switch(user_input: str) -> tuple[bool, str | None]:
    """Detect an in-band 'switch to <personality>' request; returns (True, name) or (False, None)."""
    # STT text has punctuation/casing — normalize to bare lowercase words.
    lowered = re.sub(r"[^a-z0-9\s]", "", user_input.lower())
    lowered = re.sub(r"\s+", " ", lowered).strip()
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
