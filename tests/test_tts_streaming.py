"""Tests for the ElevenLabs streaming TTS speaker.

The speaker is the **only** network-bound TTS provider we ship, and
its ``stream_speak`` is the path the engine uses in PR 3. The tests
here mock ElevenLabs entirely (no API key needed) and verify the
shape of what the speaker yields.
"""

from __future__ import annotations

from typing import Any, List
from unittest.mock import MagicMock

import pytest

from yumii.tts.speaker import YumiiSpeaker


def _make_speaker_with_chunks(chunks: List[bytes]) -> YumiiSpeaker:
    """Build a YumiiSpeaker whose underlying ``text_to_speech.stream``
    returns an iterator yielding the given raw byte chunks."""
    speaker = YumiiSpeaker.__new__(YumiiSpeaker)
    speaker.voice_id = "voice_test"
    speaker.model_id = "eleven_multilingual_v2"

    mock_client = MagicMock()

    def _fake_stream(**kwargs):
        # Return a fresh iterator each call so repeated invocations
        # don't exhaust a shared generator.
        return iter(chunks)

    mock_client.text_to_speech.stream = _fake_stream
    speaker.client = mock_client
    return speaker


@pytest.mark.asyncio
async def test_stream_speak_yields_metadata_first():
    """First yield must be the metadata dict with sample rate 22050."""
    speaker = _make_speaker_with_chunks([b"a", b"b", b"c"])

    gen = speaker.stream_speak("hello world")
    first = await gen.__anext__()
    assert first == {"type": "metadata", "sampleRate": 22050}
    await gen.aclose()


@pytest.mark.asyncio
async def test_stream_speak_yields_base64_chunks():
    """Each raw byte chunk must be base64-encoded as a string."""
    import base64

    raw_chunks = [b"hello", b"world", b"!!!"]
    expected_b64 = [base64.b64encode(c).decode("ascii") for c in raw_chunks]

    speaker = _make_speaker_with_chunks(raw_chunks)

    yielded: list[Any] = []
    async for chunk in speaker.stream_speak("hi"):
        yielded.append(chunk)

    # First is metadata, then the encoded chunks
    assert yielded[0] == {"type": "metadata", "sampleRate": 22050}
    assert yielded[1:] == expected_b64


@pytest.mark.asyncio
async def test_stream_speak_skips_empty_chunks():
    """Empty / falsy chunks from the upstream stream are skipped."""
    speaker = _make_speaker_with_chunks([b"", b"x", None, b"y"])

    yielded: list[Any] = []
    async for chunk in speaker.stream_speak("hi"):
        yielded.append(chunk)

    # metadata + 2 non-empty chunks
    assert len(yielded) == 3
    assert yielded[0] == {"type": "metadata", "sampleRate": 22050}


@pytest.mark.asyncio
async def test_stream_speak_with_empty_text_yields_nothing():
    """An empty / whitespace-only text must short-circuit — no metadata, no chunks."""
    speaker = _make_speaker_with_chunks([b"ignored"])

    yielded = [c async for c in speaker.stream_speak("")]
    assert yielded == []

    yielded = [c async for c in speaker.stream_speak("   ")]
    assert yielded == []


@pytest.mark.asyncio
async def test_stream_speak_propagates_upstream_errors():
    """If ElevenLabs raises, the speaker must re-raise so the engine
    catches it and sends an error payload to the frontend."""
    speaker = YumiiSpeaker.__new__(YumiiSpeaker)
    speaker.voice_id = "v"
    speaker.model_id = "eleven_multilingual_v2"

    mock_client = MagicMock()

    def _raise(**kwargs):
        raise RuntimeError("upstream ElevenLabs failure")

    mock_client.text_to_speech.stream = _raise
    speaker.client = mock_client

    gen = speaker.stream_speak("hi")
    # First yield (metadata) is still fine
    first = await gen.__anext__()
    assert first["type"] == "metadata"

    # Then the for-loop tries to iterate the (raising) stream and
    # the exception propagates out of __anext__.
    with pytest.raises(RuntimeError, match="upstream ElevenLabs failure"):
        await gen.__anext__()
