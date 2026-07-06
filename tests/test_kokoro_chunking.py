"""Regression tests for Kokoro's pacing-aware speech chunker.

The chunker trades off two failure modes: a huge first chunk means
seconds of silence before the voice starts; a tiny early chunk followed
by a huge one means playback outruns synthesis and stalls mid-reply.
"""

from yumii.tts.kokoro_speaker import (
    _BUDGET_GROWTH,
    _FIRST_CHUNK_BUDGET,
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


def test_run_on_sentence_splits_at_conjunction():
    text = "Hello, it's so nice to meet you and I'm here to support you in any way I can."
    chunks = _split_speech_chunks(text)
    assert len(chunks) == 2
    assert chunks[1].startswith("and ")
    assert " ".join(chunks) == text


def test_no_punctuation_falls_back_to_single_chunk():
    text = "well I suppose we could just keep talking like this without stopping"
    assert _split_speech_chunks(text) == [text]


def test_first_chunk_is_small_then_budget_grows():
    # Many short sentences: chunk sizes must respect the growing budget
    # so synthesis stays ahead of playback.
    text = "One two three. " * 20
    chunks = _split_speech_chunks(text.strip())
    assert len(chunks[0]) <= _FIRST_CHUNK_BUDGET
    delivered = len(chunks[0])
    for chunk in chunks[1:]:
        assert len(chunk) <= max(60, int(_BUDGET_GROWTH * delivered)) + 16  # +one atom slack
        delivered += len(chunk)


def test_empty_and_whitespace():
    assert _split_speech_chunks("") == []
    assert _split_speech_chunks("   ") == []
