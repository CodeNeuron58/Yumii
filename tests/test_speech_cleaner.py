"""clean_for_speech: what the model writes vs what a voice can actually say.

Nemotron 3 Super's baseline replies carried emojis ("…yesterday? 😊",
"…tomorrow. 💛") despite a 'no emojis' rule — the voice path cleans in code.
"""

import pytest

from yumii.agent.synthesizer import clean_for_speech, synthesize


@pytest.mark.parametrize("raw,spoken", [
    ("Did you survive those exams? 😊", "Did you survive those exams?"),
    ("Your code will still be there tomorrow. 💛", "Your code will still be there tomorrow."),
    ("Proud of you 👩‍💻✨!", "Proud of you!"),
    ("*smiles* Hey there.", "Hey there."),
    ("Hey there. *waves softly*", "Hey there."),
    ("I *really* mean it.", "I really mean it."),
    ("That's a **bold** move.", "That's a bold move."),
    ("Check [the docs](https://example.com) first.", "Check the docs first."),
    ("Run `pip list` now.", "Run pip list now."),
])
def test_unspeakable_text_is_cleaned(raw, spoken):
    assert clean_for_speech(raw) == spoken


def test_a_list_becomes_spoken_sentences():
    raw = "Three things:\n- eat something\n- sleep early\n1. finish the bug"
    assert clean_for_speech(raw) == "Three things: eat something. sleep early. finish the bug."


def test_headings_and_blank_lines_collapse():
    assert clean_for_speech("# Black holes\n\nThey form when stars collapse.") == (
        "Black holes. They form when stars collapse."
    )


def test_plain_speech_is_untouched():
    text = "It's about seven twenty — you've got time, but not much."
    assert clean_for_speech(text) == text


def test_synthesize_speaks_clean_text_but_keeps_the_tone():
    r = synthesize("Hey, welcome back! 😊")
    assert r.response_text == "Hey, welcome back!"
    assert r.expression != "normal"  # tone still read from the words/punctuation


def test_emoji_only_reply_speaks_nothing():
    assert synthesize("💛").response_text == ""
