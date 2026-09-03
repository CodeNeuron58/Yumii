"""Tests for KokoroSpeaker's prefetching stream_speak worker (fake model, no ONNX)."""

import asyncio
import base64
import time

import numpy as np
import pytest

from yumii.tts.kokoro_speaker import KokoroSpeaker, _split_speech_chunks

_TEXT = (
    "Hello there, it's so good to hear your voice again! "
    "I was just thinking about you, you know. "
    "What would you like to talk about today?"
)


class _FakeKokoro:
    """Stands in for kokoro_onnx.Kokoro: ~50ms of blocking 'synthesis' per call."""

    def __init__(self, delay: float = 0.05, fail_on_call: int | None = None) -> None:
        self.delay = delay
        self.fail_on_call = fail_on_call
        self.calls = 0
        self.started: list[str] = []

    def create(self, text: str, voice=None, speed=1.0, lang="en-us"):
        self.calls += 1
        self.started.append(text)
        time.sleep(self.delay)
        if self.fail_on_call is not None and self.calls == self.fail_on_call:
            raise RuntimeError("synthesis exploded")
        samples = np.zeros(int(len(text) * 0.06 * 24000) or 2400, dtype=np.float32)
        return samples, 24000


def _speaker(fake: _FakeKokoro) -> KokoroSpeaker:
    """KokoroSpeaker without __init__ (no model load, no warmup thread)."""
    s = object.__new__(KokoroSpeaker)
    s.kokoro = fake
    s.sample_rate = 24000
    s.voice = "af_heart"
    return s


@pytest.mark.asyncio
async def test_stream_yields_metadata_then_all_chunks_in_order():
    fake = _FakeKokoro(delay=0)
    s = _speaker(fake)
    items = [item async for item in s.stream_speak(_TEXT)]

    assert items[0] == {"type": "metadata", "sampleRate": 24000}
    chunks = _split_speech_chunks(_TEXT)
    assert len(items) - 1 == len(chunks)
    for item in items[1:]:
        raw = base64.b64decode(item)
        assert len(raw) % 2 == 0  # valid PCM16


@pytest.mark.asyncio
async def test_worker_prefetches_while_consumer_pauses():
    fake = _FakeKokoro(delay=0.05)
    s = _speaker(fake)
    gen = s.stream_speak(_TEXT)
    assert await gen.__anext__() == {"type": "metadata", "sampleRate": 24000}

    # Consumer pauses; the worker must keep synthesizing ahead on its own.
    await asyncio.sleep(0.25)
    assert len(fake.started) >= 2

    await gen.aclose()


@pytest.mark.asyncio
async def test_synthesis_error_propagates_to_consumer():
    fake = _FakeKokoro(delay=0, fail_on_call=2)
    s = _speaker(fake)
    received = 0
    with pytest.raises(RuntimeError):
        async for _item in s.stream_speak(_TEXT):
            received += 1
    assert received >= 1  # the chunks synthesized before the failure still arrive


@pytest.mark.asyncio
async def test_empty_text_yields_nothing_but_metadata():
    s = _speaker(_FakeKokoro(delay=0))
    items = [item async for item in s.stream_speak("   ")]
    assert items == []
