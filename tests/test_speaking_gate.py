"""Tests for the speaking gate: barge-in arming and the playback-finished handshake."""

import asyncio

import pytest

from yumii.audio.stt import (
    BARGE_IN_TRIGGER_FRAMES,
    SILERO_BARGE_THRESHOLD,
    SILENCE_END_FRAMES,
    SILERO_THRESHOLD,
    SPEECH_TRIGGER_FRAMES,
    AudioPipeline,
)
from yumii.core.engine import YumiiEngine


def test_speaking_gate_switches_pipeline_params():
    p = object.__new__(AudioPipeline)  # skip model loading
    p.speech_trigger_frames = SPEECH_TRIGGER_FRAMES
    p.speech_threshold = SILERO_THRESHOLD

    p.set_speaking_gate(armed=True)
    assert p.speech_trigger_frames == BARGE_IN_TRIGGER_FRAMES
    assert p.speech_threshold == SILERO_BARGE_THRESHOLD

    p.set_speaking_gate(armed=False)
    assert p.speech_trigger_frames == SPEECH_TRIGGER_FRAMES
    assert p.speech_threshold == SILERO_THRESHOLD


def test_barge_in_gate_is_stricter_than_normal():
    assert BARGE_IN_TRIGGER_FRAMES > SPEECH_TRIGGER_FRAMES
    assert SILERO_BARGE_THRESHOLD > SILERO_THRESHOLD
    # and the silence-end budget is untouched by the gate
    assert SILENCE_END_FRAMES == 12


def _engine() -> YumiiEngine:
    e = object.__new__(YumiiEngine)  # skip __init__ wiring
    e.interrupt_event = asyncio.Event()
    e._speech_generation = 0
    e.audio_input_queue = asyncio.Queue()
    e.is_speaking = False
    e._speak_seq = 0
    e.pipeline = None
    return e


@pytest.mark.asyncio
async def test_playback_finished_disarms_and_resets_capture():
    e = _engine()
    e._speak_seq = 3
    e.is_speaking = True

    await e.on_playback_finished(3)

    assert not e.is_speaking
    # None sentinel pushed so any echo-triggered half-capture is discarded
    assert e.audio_input_queue.qsize() == 1
    assert e.audio_input_queue.get_nowait() is None


@pytest.mark.asyncio
async def test_stale_playback_finished_is_ignored():
    e = _engine()
    e._speak_seq = 5
    e.is_speaking = True

    await e.on_playback_finished(4)  # report from the previous session

    assert e.is_speaking  # the newer session is still live
    assert e.audio_input_queue.empty()


@pytest.mark.asyncio
async def test_playback_finished_when_idle_is_noop():
    e = _engine()
    await e.on_playback_finished(0)
    assert not e.is_speaking
    assert e.audio_input_queue.empty()


@pytest.mark.asyncio
async def test_arm_increments_session_seq():
    e = _engine()
    e._arm_speaking_gate()
    assert e.is_speaking
    assert e._speak_seq == 1
    e._arm_speaking_gate()
    assert e._speak_seq == 2
    e._disarm_speaking_gate()
    assert not e.is_speaking


# ---------------------------------------------------------------------------
# tts_speaker_task streamed broadcasts. Regression for cf276e5, which
# out-dented the broadcast block out of the stream loop: she never spoke,
# and a yield-less stream misreported as "TTS failed: name 'chunk_data'".
# ---------------------------------------------------------------------------


class _StreamSpeaker:
    """stream_speak protocol: metadata dict first, then base64 chunk strings."""

    def __init__(self, chunks=("AAA", "BBB"), fail: bool = False) -> None:
        self.chunks = list(chunks)
        self.fail = fail

    async def stream_speak(self, text: str):
        yield {"type": "metadata", "sampleRate": 24000}
        for chunk in self.chunks:
            if self.fail:
                raise RuntimeError("boom")
            yield chunk


class _GatedSpeaker:
    """Same protocol with a pause between chunks — a window to trip barge-in."""

    async def stream_speak(self, text: str):
        yield {"type": "metadata", "sampleRate": 24000}
        yield "AAA"
        await asyncio.sleep(0.05)
        yield "BBB"


class _EmptySpeaker:
    """Hypothetical provider whose stream yields nothing at all."""

    async def stream_speak(self, text: str):
        return
        yield  # pragma: no cover — makes this an async generator


def _speaker_engine() -> tuple[YumiiEngine, list, list]:
    """Engine stub with a recording broadcast + gate hooks."""
    e = _engine()
    e.tts_queue = asyncio.Queue()
    sent: list = []
    disarm: list = []

    async def fake_broadcast(payload):
        sent.append(payload)

    e.broadcast_payload = fake_broadcast
    e._arm_speaking_gate = lambda: None
    e._disarm_speaking_gate = lambda: disarm.append(1)
    e._arm_playback_watchdog = lambda seq: None
    return e, sent, disarm


async def _run_speaker_until(e: YumiiEngine, done, timeout: float = 2.0, cancel: bool = True):
    """Drive tts_speaker_task until ``done()`` is true; leave it running if cancel=False."""
    task = asyncio.create_task(e.tts_speaker_task())
    try:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while not done():
            if loop.time() > deadline:
                raise TimeoutError("speaker task never reached the expected state")
            await asyncio.sleep(0.01)
    finally:
        if cancel:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    return task


def _payload(kind: str) -> dict:
    return {"kind": kind, "response": "hello", "expression": "smile", "motion": "nod"}


@pytest.mark.asyncio
async def test_streamed_tts_broadcasts_audio_start_then_chunks():
    e, sent, _ = _speaker_engine()
    e._speak_seq = 7
    e.speaker = _StreamSpeaker()
    e.tts_queue.put_nowait(_payload("stream_start"))

    await _run_speaker_until(e, lambda: len(sent) >= 3)

    assert sent[0]["type"] == "audio_start"
    assert sent[0]["sampleRate"] == 24000
    assert sent[0]["seq"] == 7
    assert sent[0]["expression"] == "smile"
    assert sent[1] == {"type": "audio_chunk", "data": "AAA"}
    assert sent[2] == {"type": "audio_chunk", "data": "BBB"}


@pytest.mark.asyncio
async def test_stream_continuation_reuses_the_open_session():
    e, sent, _ = _speaker_engine()
    e.is_speaking = True  # stream_text is dropped when no session is open
    e.speaker = _StreamSpeaker()
    e.tts_queue.put_nowait(_payload("stream_start"))
    e.tts_queue.put_nowait(_payload("stream_text"))
    e.tts_queue.put_nowait({"kind": "stream_end"})  # sentinel — processed last

    await _run_speaker_until(e, lambda: any(p["type"] == "audio_end" for p in sent))

    # opener: audio_start + chunks; continuation: chunks only (metadata skipped)
    assert [p["type"] for p in sent] == [
        "audio_start", "audio_chunk", "audio_chunk",
        "audio_chunk", "audio_chunk",
        "audio_end",
    ]


@pytest.mark.asyncio
async def test_stream_yielding_nothing_stays_silent():
    e, sent, _ = _speaker_engine()
    e.speaker = _EmptySpeaker()
    e.tts_queue.put_nowait(_payload("stream_start"))

    task = asyncio.create_task(e.tts_speaker_task())
    try:
        await asyncio.sleep(0.15)
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert sent == []  # no audio, and no "TTS failed: name 'chunk_data'" card
    assert task.cancelled()  # the task survived and is waiting for work


@pytest.mark.asyncio
async def test_stream_tts_error_sends_error_card_and_disarms():
    e, sent, disarm = _speaker_engine()
    e.speaker = _StreamSpeaker(fail=True)
    e.tts_queue.put_nowait(_payload("stream_start"))

    await _run_speaker_until(e, lambda: len(sent) >= 2)

    assert sent[0]["type"] == "audio_start"  # metadata broadcast before the failure
    card = sent[1]
    assert card["error"] == "TTS failed: boom"
    assert card["audio"] is None
    assert disarm  # gate released — she can hear the next barge-in


@pytest.mark.asyncio
async def test_generation_bump_mid_stream_stops_broadcasts_and_disarms():
    """Cancellation is a generation bump — the only thing that stops speech."""
    e, sent, disarm = _speaker_engine()
    e.speaker = _GatedSpeaker()
    e.tts_queue.put_nowait(_payload("stream_start"))

    task = await _run_speaker_until(e, lambda: len(sent) >= 2, cancel=False)
    try:
        e._speech_generation += 1  # barge-in / session switch / new turn
        await asyncio.sleep(0.12)  # _GatedSpeaker's pause — BBB would arrive here
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert [p["type"] for p in sent] == ["audio_start", "audio_chunk"]
    assert disarm  # interrupted turn released the gate


@pytest.mark.asyncio
async def test_interrupt_event_alone_does_not_stop_speech():
    """Regression for the old race: the reasoning loop cleared the shared
    interrupt_event before the speaker task observed it, so barge-in was
    silently missed. Speech is cancelled by generation bumps only — the
    event now exists solely for HITL veto state."""
    e, sent, disarm = _speaker_engine()
    e.speaker = _GatedSpeaker()
    e.tts_queue.put_nowait(_payload("stream_start"))

    task = await _run_speaker_until(e, lambda: len(sent) >= 3, cancel=False)
    try:
        e.interrupt_event.set()
        await asyncio.sleep(0.12)  # _GatedSpeaker's pause — BBB arrives here
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert [p["type"] for p in sent] == ["audio_start", "audio_chunk", "audio_chunk"]
    assert not disarm


@pytest.mark.asyncio
async def test_stale_generation_payload_is_dropped():
    """Speech queued under an older generation never plays — this is what
    drops the previous turn's still-queued sentences when a new turn starts."""
    e, sent, _ = _speaker_engine()
    e.speaker = _StreamSpeaker()
    e.tts_queue.put_nowait({**_payload("stream_start"), "gen": 0})
    e._speech_generation = 1  # a cancellation happened after it was queued

    task = asyncio.create_task(e.tts_speaker_task())
    try:
        await asyncio.sleep(0.1)
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert sent == []  # stale audio dropped, no broadcasts, no crash
    assert e.tts_queue.empty()
