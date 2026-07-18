"""Synthesizer: derive expression + motion from the agent's text via ordered regex heuristics.

Deterministic, no LLM — the same text always yields the same result. First
matching pattern wins (most specific first). Labels are pinned by
:class:`yumii.agent.llm.YumiiResponse` and must match the personality prompts.
"""

from __future__ import annotations

import re
from typing import Literal

from yumii.agent.llm import YumiiResponse

ExpressionLabel = Literal[
    "smile", "angry", "sad", "surprise", "scared", "shy", "normal",
]
MotionLabel = Literal[
    "nod", "shakehead", "tilthead", "fidget", "forward", "lookaway",
    "greeting", "idle",
]

# Frozen sets for runtime validation — a bad value coerces to normal/idle, never crashes.
VALID_EXPRESSIONS: frozenset[str] = frozenset(
    {"smile", "angry", "sad", "surprise", "scared", "shy", "normal"},
)
VALID_MOTIONS: frozenset[str] = frozenset(
    {"nod", "shakehead", "tilthead", "fidget", "forward", "lookaway", "greeting", "idle"},
)


# ----------------------------------------------------------------------
# Pattern tables
# ----------------------------------------------------------------------
# Scanned in order; first match wins, most specific first. Case-insensitive.
# angry before surprise so "!!" (angry) isn't stolen by surprise's bare "!".
_EXPRESSION_PATTERNS: list[tuple[ExpressionLabel, re.Pattern[str]]] = [
    # Anger / frustration — `!!` is a strong tell, must beat surprise's `!`
    ("angry", re.compile(
        r"\b("
        r"angry|mad|furious|annoyed|frustrated|hate|terrible|"
        r"awful|horrible|wtf|damn|ugh|grr|"
        r"stop|cut it out|shut up"
        r")\b|!{2,}",
        re.IGNORECASE,
    )),
    # Surprise / curiosity — bare `!`/`?`, `?!`, `!?`, or surprise words
    ("surprise", re.compile(
        r"\b("
        r"wow|whoa|oh!?|really|seriously|unbelievable|"
        r"amazing|incredible|no way|huh|"
        r"interesting|fascinating|curious|"
        r"surprise(?:d)?|astonished|stunned"
        r")\b|!|\?|\?!|\!\?",
        re.IGNORECASE,
    )),
    # Sadness / sympathy — `...` is a strong tell
    ("sad", re.compile(
        r"\b("
        r"sad|sorry|unfortunately|miss(?:ing|ed)?|lost|regret|wish|"
        r"alone|lonely|tired|exhausted|hurts?|pain|tears?|"
        r"my condolences|condolences|"
        r"\bi'?m sorry\b"
        r")\b|\.{3}",
        re.IGNORECASE,
    )),
    # Fear / anxiety
    ("scared", re.compile(
        r"\b("
        r"scared|afraid|frightened|terrified|worried|anxious|nervous|"
        r"danger(?:ous)?|warning|alert|panic"
        r")\b",
        re.IGNORECASE,
    )),
    # Shyness / soft agreement — `...` and hesitations beat smile
    ("shy", re.compile(
        r"\b("
        r"shy|blush(?:ing)?|embarrassed|hehe|tee ?hee|"
        r"um+m?|er+m?|uh+h?|"
        r"maybe|perhaps|might"
        r")\b",
        re.IGNORECASE,
    )),
    # Greeting / warmth — positive valence, friendly verbs (no bare `!`)
    ("smile", re.compile(
        r"\b("
        r"hi|hello|hey|yo|welcome|nice to (?:meet|see|hear)|"
        r"love|lovely|wonderful|glad|happy|excited|"
        r"thanks|thank you|yay|congrats|congratulations|"
        r"awesome|fantastic|perfect|sure|okay|ok|alright|"
        r"heh+|haha|lol|hoho|joy|delight|pleased"
        r")\b",
        re.IGNORECASE,
    )),
    # Default fallback — pattern that can never match
    ("normal", re.compile(r"(?!)")),
]


_MOTION_PATTERNS: list[tuple[MotionLabel, re.Pattern[str]]] = [
    # Greeting opener — always a wave/tilt on first contact
    ("greeting", re.compile(
        r"^\s*(?:hi|hello|hey|yo|welcome|greetings|good (?:morning|afternoon|evening))",
        re.IGNORECASE,
    )),
    # Agreement / affirmation
    ("nod", re.compile(
        r"\b("
        r"yes|yeah|yep|sure|definitely|absolutely|exactly|right|"
        r"agreed|correct|true|indeed|"
        r"of course|you'?re right"
        r")\b",
        re.IGNORECASE,
    )),
    # Curiosity / question
    ("tilthead", re.compile(
        r"\b("
        r"why|how|what|when|where|who|which|"
        r"curious|wonder|interesting\?|"
        r"could you|would you|do you|can you|may i|"
        r"\?$|\?\s"
        r")",
        re.IGNORECASE,
    )),
    # Shy / lookaway — must come BEFORE shakehead so "don't look" doesn't
    # get swallowed by the negation pattern. NO outer \b wrapper because
    # \.\.\. is non-word chars and \b...\b can't anchor around it.
    ("lookaway", re.compile(
        r"\b(shy|blush|embarrassed|secret|hehe)\b"
        r"|\.\.\."
        r"|\bum+m\b|\ber+m\b"
        r"|don'?t look",
        re.IGNORECASE,
    )),
    # Disagreement / negation
    ("shakehead", re.compile(
        r"\b("
        r"no|nope|nah|never|not really|incorrect|wrong|"
        r"don'?t|doesn'?t|won'?t|"
        r"i disagree|sorry,? but"
        r")\b",
        re.IGNORECASE,
    )),
    # Forward lean / engagement — verbal cues only, no bare `!`
    ("forward", re.compile(
        r"\b("
        r"listen|look|check this out|here'?s|"
        r"i'?ll show you|let'?s|follow me|come on|"
        r"important|attention|wait|hold on"
        r")\b",
        re.IGNORECASE,
    )),
    # Fidget / energy (genki-style)
    ("fidget", re.compile(
        r"\b("
        r"yay|wheee|let'?s go|come on|"
        r"yatta|banzai|woohoo|"
        r"!{2,}|w+!+"
        r")\b",
        re.IGNORECASE,
    )),
    # Default fallback — pattern that can never match
    ("idle", re.compile(r"(?!)")),
]


# ----------------------------------------------------------------------
# Classifier
# ----------------------------------------------------------------------


def _classify(text: str, patterns: list[tuple[str, re.Pattern[str]]]) -> str:
    """Return the first label whose regex matches ``text``, or the last
    entry's label (the "default fallback"). The caller is expected to
    pass a list whose final entry is the fallback.
    """
    fallback = patterns[-1][0]
    for label, pattern in patterns[:-1]:
        if pattern.search(text):
            return label
    return fallback


def _expression_for(text: str) -> ExpressionLabel:
    """Pick an expression label from the agent text (``normal`` if nothing matches)."""
    if not text:
        return "normal"
    label = _classify(text, _EXPRESSION_PATTERNS)
    return label if label in VALID_EXPRESSIONS else "normal"


def _motion_for(text: str) -> MotionLabel:
    """Pick a motion label from the agent text (``idle`` if nothing matches)."""
    if not text:
        return "idle"
    label = _classify(text, _MOTION_PATTERNS)
    return label if label in VALID_MOTIONS else "idle"


# Public entry point ----------------------------------------------------

# Strip <think>…</think> so a model's private reasoning never reaches TTS.
_THINK_BLOCK = re.compile(
    r"<think(?:ing)?>.*?</think(?:ing)?>\s*", re.DOTALL | re.IGNORECASE
)


def synthesize(agent_text: str) -> YumiiResponse:
    """Convert agent text into a YumiiResponse (deterministic; empty text → safe default)."""
    text = _THINK_BLOCK.sub("", agent_text or "").strip()
    if not text:
        return YumiiResponse(
            response_text="...",
            expression="normal",
            motion="idle",
        )
    return YumiiResponse(
        response_text=text,
        expression=_expression_for(text),
        motion=_motion_for(text),
    )


__all__ = [
    "YumiiResponse",
    "ExpressionLabel",
    "MotionLabel",
    "VALID_EXPRESSIONS",
    "VALID_MOTIONS",
    "synthesize",
    "_expression_for",
    "_motion_for",
]
