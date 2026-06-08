"""Tests for the deterministic emotion + motion synthesizer.

The synthesizer is a regex-based classifier. The tests below are the
*behavioural spec* — they pin down the rules in
``src/yumii/agent/synthesizer.py``.

Design contract (kept in sync with the module docstring):

* A bare ``!`` or ``?`` is *surprise*, not smile (an exclamation is
  astonishment, not necessarily joy).
* ``!!`` is *angry* (escalation = frustration).
* ``...`` is *sad* (trailing off, hesitation).
* A question at end of sentence is *surprise*; mid-sentence is
  *tilthead* (curiosity).
* Words like "wonderful", "thanks", "yay", "haha" → *smile*.
* Words like "um", "shy", "secret" → *shy* / *lookaway*.
* Greeting openers ("Hi!", "Hello!") → *greeting* motion.
* Plain text → ``"normal"`` expression, ``"idle"`` motion.
* Order matters: the first pattern that matches wins.

* **Prompt contract.** Personality prompts must not list label words
  (``smile``, ``nod``, ``tilthead``, etc.) as choices the LLM should
  "select" — that trains the LLM to emit the label words as text,
  which the synthesizer then misreads as the actual labels. The
  CRITICAL RULE in each prompt must forbid label emission in plain
  text, and the EXPRESSION & MOTION ALIGNMENT / AVAILABLE * lists
  must be absent. See ``test_personality_prompts_do_not_leak_labels``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from yumii.agent.llm import YumiiResponse
from yumii.agent.synthesizer import (
    VALID_EXPRESSIONS,
    VALID_MOTIONS,
    _expression_for,
    _motion_for,
    synthesize,
)


# ----------------------------------------------------------------------
# synthesize() — the public entry point
# ----------------------------------------------------------------------


def test_synthesize_returns_yumii_response():
    """The public function must return a YumiiResponse instance."""
    result = synthesize("Hello there!")
    assert isinstance(result, YumiiResponse)


def test_synthesize_preserves_text():
    """The text returned must be the trimmed input (not a transformation)."""
    text = "  Hi there!  "
    result = synthesize(text)
    assert result.response_text == "Hi there!"


def test_synthesize_empty_text_returns_safe_default():
    """Empty / None-ish input must NOT crash. It returns a safe placeholder."""
    assert synthesize("") == YumiiResponse(
        response_text="...", expression="normal", motion="idle",
    )
    assert synthesize("   ") == YumiiResponse(
        response_text="...", expression="normal", motion="idle",
    )
    # None-ish must not raise either — the function guards with `or ""`.
    assert synthesize(None).expression == "normal"  # type: ignore[arg-type]


def test_synthesize_expression_is_always_valid():
    """No matter what nonsense we throw at it, the label must be valid."""
    for text in [
        "", "hello", "YES", "no", "!!!", "what??", "lol", "...",
        "a" * 100, "?!?!?!", "hmm", "goodbye",
    ]:
        result = synthesize(text)
        assert result.expression in VALID_EXPRESSIONS, text


def test_synthesize_motion_is_always_valid():
    """No matter what nonsense we throw at it, the motion must be valid."""
    for text in [
        "", "hello", "YES", "no", "!!!", "what??", "lol", "...",
        "a" * 100, "?!?!?!", "hmm", "goodbye",
    ]:
        result = synthesize(text)
        assert result.motion in VALID_MOTIONS, text


# ----------------------------------------------------------------------
# Expression heuristics
# ----------------------------------------------------------------------


@pytest.mark.parametrize("text,expected", [
    # Surprise from punctuation
    ("Hello!", "surprise"),
    ("What?", "surprise"),
    ("Wow!", "surprise"),
    # Surprise from vocabulary
    ("Wow, that's amazing", "surprise"),
    ("What?!", "surprise"),
    ("Really??", "surprise"),
    # Anger — vocabulary
    ("I'm so angry", "angry"),
    ("That's terrible", "angry"),
    ("Stop it", "angry"),
    # Anger — punctuation escalation
    ("Stop!!", "angry"),
    # Sad — vocabulary
    ("I'm sorry to hear that", "sad"),
    ("Unfortunately", "sad"),
    ("My condolences", "sad"),
    # Sad — trailing dots
    ("...", "sad"),
    ("Well...", "sad"),
    # Scared
    ("I'm scared", "scared"),
    ("That's dangerous", "scared"),
    # Shy
    ("Um, maybe", "shy"),
    ("hehe", "shy"),
    ("er, not sure", "shy"),
    # Smile — positive words (no bare `!` or `?` needed)
    ("That's wonderful", "smile"),
    ("Thanks so much", "smile"),
    ("Yay", "smile"),
    ("haha that's funny", "smile"),
    # Plain text -> normal
    ("The function returns a value.", "normal"),
    ("", "normal"),
    ("goodbye", "normal"),
])
def test_expression_for(text, expected):
    assert _expression_for(text) == expected


# ----------------------------------------------------------------------
# Motion heuristics
# ----------------------------------------------------------------------


@pytest.mark.parametrize("text,expected", [
    # Greeting openers (anchored at start of text)
    ("Hello there!", "greeting"),
    ("Hi!", "greeting"),
    ("Good morning!", "greeting"),
    ("Welcome!", "greeting"),
    # Affirmations
    ("Yes, I agree", "nod"),
    ("Of course!", "nod"),
    # Negations
    ("No, that's wrong", "shakehead"),
    ("I don't think so", "shakehead"),
    # Questions / curiosity
    ("Why did that happen?", "tilthead"),
    ("How does that work?", "tilthead"),
    ("What do you mean?", "tilthead"),
    # Engagement / forward
    ("Listen carefully!", "forward"),
    ("Check this out!", "forward"),
    # Lookaway / shy
    ("Um... maybe later", "lookaway"),
    ("It's a secret", "lookaway"),
    ("don't look", "lookaway"),
    # Fidget / energy
    ("Yay!!", "fidget"),
    ("woohoo", "fidget"),
    # Plain text -> idle
    ("The function returns a value.", "idle"),
    ("", "idle"),
])
def test_motion_for(text, expected):
    assert _motion_for(text) == expected


# ----------------------------------------------------------------------
# Determinism — same input, same output
# ----------------------------------------------------------------------


def test_synthesize_is_deterministic():
    """Provider-agnostic guarantee: same text -> same response every time."""
    text = "Wow, that's amazing! Let me show you."
    results = [synthesize(text) for _ in range(5)]
    first = results[0]
    for r in results[1:]:
        assert r == first


def test_synthesize_does_not_modify_input_text_casing():
    """Original casing is preserved in the response (regex is case-insensitive,
    but the output text is not transformed)."""
    result = synthesize("WOW that's AMAZING")
    assert result.response_text == "WOW that's AMAZING"
    # The classifier still fires on caps (e.g. surprise on "wow")
    assert result.expression in VALID_EXPRESSIONS


# ----------------------------------------------------------------------
# Order matters — more specific patterns beat generic ones
# ----------------------------------------------------------------------


def test_surprise_vocabulary_beats_smile_for_wonderful():
    """A "Wow" wins over "wonderful" because the surprise pattern comes first."""
    assert _expression_for("Wow, that's wonderful!") == "surprise"


def test_angry_beats_surprise_for_double_bang():
    """!! triggers angry's specific pattern even though ! alone triggers surprise."""
    assert _expression_for("Stop!!") == "angry"


def test_greeting_motion_overrides_affirmation():
    """A 'Hi, yes, I will' starts with the greeting anchor and stays greeting."""
    assert _motion_for("Hi! Yes, I will do it.") == "greeting"


def test_sad_beats_smile_for_thanks_with_dots():
    """'Thanks...' has both thanks (smile) and ... (sad). Sad wins by order."""
    assert _expression_for("Thanks...") == "sad"


# ----------------------------------------------------------------------
# Prompt contract — no label-leak from personality prompts
# ----------------------------------------------------------------------
#
# Regression: in pre-v1.0 the personality .txt files included an
# ``EXPRESSION & MOTION ALIGNMENT`` section that listed labels like
# ``'smile'`` and ``'nod'`` in single quotes, as if the LLM should
# pick one. The LLM dutifully picked — by *saying* the words at the
# end of its reply ("...smile and nod."), which the synthesizer then
# misread as actual labels. v1.0 removes those sections and adds a
# CRITICAL RULE at the top of every prompt. This test pins the new
# contract: any future prompt edit that re-introduces label listings
# is caught here.


_PROMPTS_DIR = (
    Path(__file__).resolve().parent.parent
    / "src" / "yumii" / "assets" / "prompts"
)

# Section headers that must NOT appear in any personality prompt. They
# are listed with their exact wording so that a near-miss (different
# phrasing) won't get caught — only the actual offender.
_FORBIDDEN_SECTIONS = (
    "EXPRESSION & MOTION ALIGNMENT",
    "AVAILABLE FACIAL EXPRESSIONS",
    "AVAILABLE BODY MOTIONS",
)

_PERSONALITY_NAMES = ("caring", "tsundere", "genki", "kuudere", "yandere", "dandere")


def _load_prompts() -> dict[str, str]:
    """Load all personality prompt files, keyed by stem."""
    return {
        p.stem: p.read_text(encoding="utf-8")
        for p in _PROMPTS_DIR.glob("*.txt")
    }


def test_all_six_personalities_have_prompts() -> None:
    """Sanity: the test directory actually contains the 6 expected prompts."""
    names = set(_load_prompts())
    assert names == set(_PERSONALITY_NAMES), (
        f"expected 6 personalities, got {sorted(names)}"
    )


@pytest.mark.parametrize("name", _PERSONALITY_NAMES)
def test_personality_prompts_do_not_leak_labels(name: str) -> None:
    """Each personality prompt must not contain label-listing sections.

    These sections train the LLM to emit label words ("smile", "nod",
    "tilthead", etc.) as text in its reply. The synthesizer then
    misreads them as the actual emotion / motion. v1.0 forbids them.
    """
    prompts = _load_prompts()
    assert name in prompts, f"missing personality prompt: {name}"
    text = prompts[name]
    for section in _FORBIDDEN_SECTIONS:
        assert section not in text, (
            f"{name}.txt still contains forbidden section {section!r}. "
            "This trains the LLM to emit label words as text. "
            "Delete the section and rely on the CRITICAL RULE."
        )


@pytest.mark.parametrize("name", _PERSONALITY_NAMES)
def test_personality_prompts_have_critical_rule_first(name: str) -> None:
    """The CRITICAL RULE must be in the first ~5 non-blank lines of every prompt.

    Putting it at the top (rather than the bottom) means the LLM sees
    "speak plainly, the system handles labels" *before* it sees the
    personality guidance. The wording must also specifically forbid
    JSON, function tags, *and* emotion labels — all three.
    """
    prompts = _load_prompts()
    assert name in prompts
    text = prompts[name]
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert len(lines) >= 3, f"{name}.txt is suspiciously short"
    head = "\n".join(lines[:5])
    assert "CRITICAL RULE" in head, (
        f"{name}.txt does not start with a CRITICAL RULE block. "
        "Move it to the top of the file."
    )
    assert "JSON" in text, f"{name}.txt CRITICAL RULE does not forbid JSON"
    assert "function tag" in text or "function-call" in text, (
        f"{name}.txt CRITICAL RULE does not forbid function tags"
    )
    assert "emotion label" in text or "labels" in text, (
        f"{name}.txt CRITICAL RULE does not forbid emotion labels"
    )
