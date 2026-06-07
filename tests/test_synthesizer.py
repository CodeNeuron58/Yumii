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
"""

from __future__ import annotations

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
