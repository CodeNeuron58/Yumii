"""Time-related tools for Yumii.

A native LangChain tool, registered on the global :data:`yumii.tools.registry.registry`
with a READ policy (no confirmation gate, no external blast radius).
"""

from __future__ import annotations

import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from yumii.tools.policy import ToolCategory, ToolPolicy
from yumii.tools.registry import register


class TimeInput(BaseModel):
    """Input schema for :func:`get_current_time`.

    Attributes:
        tz: Optional IANA timezone name, e.g. ``"America/New_York"``.
            If omitted, defaults to the system's local timezone.
    """

    tz: str | None = Field(
        default=None,
        description=(
            "Optional IANA timezone name such as 'America/New_York' or "
            "'Europe/London'. Defaults to the system's local timezone "
            "when omitted."
        ),
    )


@tool("get_current_time", args_schema=TimeInput)
def get_current_time(tz: str | None = None) -> str:
    """Get the current time, optionally in a specific timezone.

    Use this whenever the user asks "what time is it?" or wants a
    timestamp in a particular location. Returns the time formatted as
    ``HH:MM AM/PM``. If ``tz`` is omitted, returns the system's local
    time.
    """
    if tz:
        try:
            zone = ZoneInfo(tz)
        except ZoneInfoNotFoundError:
            return f"Unknown timezone: {tz!r}"
    else:
        zone = datetime.datetime.now().astimezone().tzinfo
    return datetime.datetime.now(zone).strftime("%I:%M %p")


# Register on the global registry with a READ policy.
# Pure read, no side effects, no confirmation needed.
register(
    get_current_time,
    ToolPolicy(
        category=ToolCategory.READ,
        requires_confirmation=False,
    ),
)


__all__ = ["get_current_time", "TimeInput"]
