"""ToolPolicy metadata: ``category`` drives the HITL gate; other fields are reserved (unused)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ToolCategory(str, Enum):
    """Risk class driving the HITL gate: READ (none), WRITE (local), EXTERNAL (gate by default)."""

    READ = "read"
    WRITE = "write"
    EXTERNAL = "external"


@dataclass(frozen=True)
class ToolPolicy:
    """How a tool is invoked: requires_confirmation + category (other fields reserved, unused)."""

    requires_confirmation: bool = False
    category: ToolCategory = ToolCategory.READ
    idempotency_key: str | None = None
    description_override: str | None = None


# Recommended policy per category — callers can override individual fields.
DEFAULT_POLICIES: dict[ToolCategory, ToolPolicy] = {
    ToolCategory.READ: ToolPolicy(
        requires_confirmation=False,
        category=ToolCategory.READ,
    ),
    ToolCategory.WRITE: ToolPolicy(
        requires_confirmation=False,
        category=ToolCategory.WRITE,
    ),
    ToolCategory.EXTERNAL: ToolPolicy(
        requires_confirmation=True,
        category=ToolCategory.EXTERNAL,
    ),
}


def default_policy_for(category: ToolCategory) -> ToolPolicy:
    """Return the recommended policy for a category."""
    return DEFAULT_POLICIES[category]


__all__ = [
    "ToolCategory",
    "ToolPolicy",
    "DEFAULT_POLICIES",
    "default_policy_for",
]
