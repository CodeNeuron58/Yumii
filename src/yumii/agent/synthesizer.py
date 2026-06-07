"""Synthesizer — converts a plain LLM response into a YumiiResponse.

PR 2 ships a **placeholder** synthesizer that always returns
``expression="normal"`` and ``motion="idle"``. The engine contract
reads these fields from the graph output, so the placeholder keeps
the wiring honest.

PR 3 will replace the body of :func:`synthesize` with a deterministic
heuristic classifier (regex-based emotion + motion detection) so the
heuristic runs in <1 ms, is deterministic, and works identically with
every LLM provider — no second LLM call, no Groq-specific behaviour.
"""

from __future__ import annotations

from typing import Literal

# --- Re-use the YumiiResponse class from llm.py -------------------------
# We re-import rather than re-declare so the engine sees one type, not
# two divergent ones.
from yumii.agent.llm import YumiiResponse

# Allowed values for the structured fields. These must stay in lock-
# step with the comments in llm.py and the Live2D model's animation
# map in the frontend.
ExpressionLabel = Literal[
    "smile", "angry", "sad", "surprise", "scared", "shy", "normal",
]
MotionLabel = Literal[
    "nod", "shakehead", "tilthead", "fidget", "forward", "lookaway",
    "greeting", "idle",
]


def synthesize(agent_text: str) -> YumiiResponse:
    """Convert a plain agent response into a YumiiResponse.

    PR 2 placeholder: always returns ``expression="normal"`` and
    ``motion="idle"``. PR 3 will run a regex-based heuristic to pick
    an emotion and a motion from ``agent_text``.

    Args:
        agent_text: The raw text the agent emitted. May be empty (e.g.
            if the LLM returned a tool_calls-only AIMessage) — callers
            should not invoke the synthesizer on empty text. We guard
            here anyway with a sane default.

    Returns:
        A :class:`YumiiResponse` with the three fields the engine and
        the frontend both consume.
    """
    text = (agent_text or "").strip()
    if not text:
        return YumiiResponse(
            response_text="...",
            expression="normal",
            motion="idle",
        )
    return YumiiResponse(
        response_text=text,
        expression="normal",
        motion="idle",
    )


__all__ = [
    "YumiiResponse",
    "ExpressionLabel",
    "MotionLabel",
    "synthesize",
]
