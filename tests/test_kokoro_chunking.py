"""Regression tests for Kokoro's speech chunker.

Chunk budgets exist for latency and interrupt-responsiveness only — the
prefetch worker (stream_speak) is what keeps synthesis ahead of playback.
Small opener chunk = fast first word; steady chunks stay short so an
in-flight synthesis never outlives a barge-in by long.
"""

from yumii.tts.kokoro_speaker import (
    _FIRST_CHUNK_BUDGET,
    _STEADY_BUDGET,
    _split_speech_chunks,
)


def test_multi_sentence_reply_splits():
    text = (
        "Hello there, it's so good to hear your voice again! "
        "I was just thinking about you, you know. "
        "What would you like to talk about today?"
    )
    chunks = _split_speech_chunks(text)
    assert len(chunks) >= 3
    assert len(chunks[0]) <= _FIRST_CHUNK_BUDGET
    # nothing lost or reordered
    assert " ".join(chunks) == text


def test_long_run_on_sentence_splits_at_conjunction():
    text = (
        "Hello there, it's been such a long day and I have been waiting "
        "for the chance to talk with you about everything that happened "
        "since this morning."
    )
    chunks = _split_speech_chunks(text)
    assert len(chunks) >= 3
    assert any(c.startswith("and ") for c in chunks)
    assert " ".join(chunks) == text


def test_no_punctuation_falls_back_to_single_chunk():
    text = "well I suppose we could just keep talking like this without stopping"
    assert _split_speech_chunks(text) == [text]


def test_first_chunk_is_small_then_steady():
    text = "One two three. " * 20
    chunks = _split_speech_chunks(text.strip())
    assert len(chunks[0]) <= _FIRST_CHUNK_BUDGET
    for chunk in chunks[1:]:
        # +slack for a single un-splittable atom packed alone
        assert len(chunk) <= _STEADY_BUDGET + 80


def test_empty_and_whitespace():
    assert _split_speech_chunks("") == []
    assert _split_speech_chunks("   ") == []
