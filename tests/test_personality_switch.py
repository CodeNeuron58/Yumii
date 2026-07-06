"""Regression tests for the voice personality-switch detector.

STT output (Whisper/Groq) carries punctuation and casing; the detector
must still recognise switch phrases like "Switch to tsundere."
"""

from yumii.agent.nodes import check_personality_switch


def test_exact_phrase_matches():
    is_switch, personality = check_personality_switch("switch to tsundere")
    assert is_switch
    assert personality == "tsundere"


def test_bare_personality_name_matches():
    is_switch, personality = check_personality_switch("genki")
    assert is_switch
    assert personality == "genki"


def test_stt_punctuation_and_casing_still_match():
    for utterance in (
        "Switch to tsundere.",
        "Tsundere!",
        "  Become genki?  ",
        "Be kuudere,",
    ):
        is_switch, personality = check_personality_switch(utterance)
        assert is_switch, f"should switch on: {utterance!r}"
        assert personality in {"tsundere", "genki", "kuudere"}


def test_normal_conversation_does_not_switch():
    for utterance in (
        "tell me about tsundere characters",
        "what time is it?",
        "I met a genki person today",
    ):
        is_switch, personality = check_personality_switch(utterance)
        assert not is_switch, f"should NOT switch on: {utterance!r}"
        assert personality is None
