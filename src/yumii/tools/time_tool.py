"""get_current_time — a READ tool for the current time (optional timezone)."""

from __future__ import annotations

import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from yumii.tools.policy import ToolCategory, ToolPolicy
from yumii.tools.registry import register


class TimeInput(BaseModel):
    """Input schema for :func:`get_current_time`."""

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


# READ tool — pure read, no side effects, no confirmation needed.
register(
    get_current_time,
    ToolPolicy(
        category=ToolCategory.READ,
        requires_confirmation=False,
    ),
)


__all__ = ["get_current_time", "TimeInput"]
