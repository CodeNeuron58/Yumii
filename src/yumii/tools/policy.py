"""Tool policy metadata for Yumii's tool registry.

A ``ToolPolicy`` is hung off every registered tool and tells the agent
graph two things that the bare ``@tool`` decorator cannot:

* **Risk classification** — ``category`` (read/write/external) drives
  whether the tool needs a confirmation gate before running.
* **Idempotency** — ``idempotency_key`` is used by the Planner node to
  de-duplicate steps in a multi-step plan (e.g. "check the weather in
  Tokyo" should only run once even if the LLM emits it twice).

The policy is plain data; it has no behaviour. The graph reads it via
:func:`yumii.tools.registry.ToolRegistry.list_policies`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ToolCategory(str, Enum):
    """Risk classification for a tool.

    Used by the agent graph to decide whether the tool needs a
    human-in-the-loop confirmation gate before execution.

    * ``READ`` — pure read, no side effects, no confirmation needed.
    * ``WRITE`` — mutates local state (e.g. creates a fact, archives a
      session). No external blast radius, but worth surfacing in the UI.
    * ``EXTERNAL`` — talks to a third-party service (Gmail, Calendar,
      Stripe). Default to requiring confirmation.
    """

    READ = "read"
    WRITE = "write"
    EXTERNAL = "external"


@dataclass(frozen=True)
class ToolPolicy:
    """Metadata about how a tool should be invoked.

    Attributes:
        requires_confirmation: If True, the graph will pause before
            running this tool and emit a ``confirmation_request`` event
            to the browser. The user must approve before execution
            resumes. Defaults to False for ``READ`` tools, True for
            ``EXTERNAL`` tools, False for ``WRITE`` tools (configurable
            per tool).
        category: Risk classification. See :class:`ToolCategory`.
        idempotency_key: Optional string the Planner uses to de-duplicate
            steps in a multi-step plan. Two tools with the same
            idempotency_key should not both be invoked in the same
            plan. If None, the tool is treated as non-idempotent.
        description_override: Optional string that overrides the
            tool's docstring as the description shown to the LLM.
            Useful for tuning the Planner's tool selection without
            editing the tool's actual docstring.
    """

    requires_confirmation: bool = False
    category: ToolCategory = ToolCategory.READ
    idempotency_key: str | None = None
    description_override: str | None = None


# Sensible defaults for each category, so callers can write
# ``ToolPolicy(category=ToolCategory.EXTERNAL)`` and get the right
# ``requires_confirmation`` value without repeating the rule.
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
    """Return the recommended policy for a given category.

    The caller can then override individual fields:

    .. code-block:: python

        policy = default_policy_for(ToolCategory.EXTERNAL)
        # policy.requires_confirmation is True by default
    """
    return DEFAULT_POLICIES[category]


__all__ = [
    "ToolCategory",
    "ToolPolicy",
    "DEFAULT_POLICIES",
    "default_policy_for",
]
