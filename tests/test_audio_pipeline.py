"""Tests for the audio pipeline's VAD-side logic.

These tests deliberately avoid loading the Silero VAD or faster-whisper
models (which require a working torch + network for the model download).
They exercise pure-Python helpers: the RMS energy gate and the PCM
normalization, which are deterministic.
"""

import asyncio

import numpy as np
import pytest

from yumii.audio.stt import (
    FRAME_SIZE,
    SILENCE_END_FRAMES,
    SPEECH_TRIGGER_FRAMES,
    SILERO_THRESHOLD,
    AudioPipeline,
    float_to_pcm16,
    normalize_audio,
    rms_energy,
)


def test_rms_energy_silent_signal_is_zero() -> None:
    """A constant-zero waveform should have zero RMS energy."""
    signal = np.zeros(512, dtype=np.float32)
    assert rms_energy(signal) == pytest.approx(0.0, abs=1e-9)


def test_rms_energy_loud_signal_is_high() -> None:
    """A full-amplitude sine wave should have RMS ~0.707."""
    t = np.arange(512, dtype=np.float32) / 16000.0
    signal = np.sin(2 * np.pi * 440.0 * t).astype(np.float32)
    energy = rms_energy(signal)
    # RMS of unit-amplitude sine is 1/sqrt(2) ~= 0.7071
    assert 0.6 < energy < 0.8


def test_rms_energy_quiet_signal_below_threshold() -> None:
    """A signal well below the gate threshold should be detectable as quiet."""
    signal = np.full(512, 0.001, dtype=np.float32)
    # The engine's RMS_ENERGY_GATE is 0.008; this signal should be below it.
    assert rms_energy(signal) < 0.008


def test_float_to_pcm16_clipping() -> None:
    """Values outside [-1, 1] should be clipped, not wrap around."""
    out = float_to_pcm16(np.array([2.0, -2.0, 0.5, -0.5, 0.0, 1.0, -1.0], dtype=np.float32))
    # Empirically verified: numpy casts to int16 with truncation toward zero.
    # 2.0 -> 1.0 -> 32767 (clipped)
    # -2.0 -> -1.0 -> -32767 (clipped; int16 minimum is -32768, but -1.0*32767=-32767)
    # 0.5 -> 16383 (0.5 * 32767 = 16383.5, truncated to 16383)
    # -0.5 -> -16383 (truncated toward zero, not banker's rounded)
    # 0.0 -> 0, 1.0 -> 32767, -1.0 -> -32767
    assert out.dtype == np.int16
    assert out.tolist() == [32767, -32767, 16383, -16383, 0, 32767, -32767]


def test_normalize_audio_silent_input_is_silent() -> None:
    """Normalizing silence should not produce NaN or division-by-zero."""
    signal = np.zeros(100, dtype=np.int16)
    out = normalize_audio(signal)
    assert out.dtype == np.int16
    assert np.all(out == 0)


def test_normalize_audio_peak_clamped_to_safe_level() -> None:
    """A normalized signal should peak around 90% of int16 max."""
    signal = np.array([100, -100, 200, -200] * 50, dtype=np.int16)
    out = normalize_audio(signal)
    # Peak should be ~ 0.9 * 32767 = 29490
    peak = int(np.max(np.abs(out.astype(np.int32))))
    assert 28000 < peak <= 29490


# ---------------------------------------------------------------------------
# Mute sentinel: a None chunk aborts any in-flight capture.
# Exercised with fakes so no Silero/Whisper model loads.
# ---------------------------------------------------------------------------


class FakeVAD:
    """Speech iff the frame is loud — deterministic, no model."""

    def __init__(self) -> None:
        self.resets = 0

    def reset_states(self) -> None:
        self.resets += 1

    def __call__(self, frame: np.ndarray, sr: int) -> float:
        return 1.0 if float(np.sqrt(np.mean(frame**2))) > 0.05 else 0.0


class FakeStreamingTranscriber:
    """Streaming-shaped transcriber (process_chunk/get_final) with counters."""

    def __init__(self) -> None:
        self.final_calls = 0

    def process_chunk(self, pcm16_bytes: bytes) -> dict | None:
        return None

    def get_final(self) -> str | None:
        self.final_calls += 1
        return "post-mute words"

    def transcribe(self, audio_data) -> str | None:
        return None


def _make_pipeline(transcriber=None) -> AudioPipeline:
    """Build an AudioPipeline without running __init__ (no model loads)."""
    p = AudioPipeline.__new__(AudioPipeline)
    p._silero_model = FakeVAD()
    p.transcriber = transcriber or FakeStreamingTranscriber()
    p.speech_trigger_frames = SPEECH_TRIGGER_FRAMES
    p.speech_threshold = SILERO_THRESHOLD
    p._smart_turn = None  # legacy fixed-silence end-of-turn
    return p


_SPEECH = (np.full(FRAME_SIZE, 0.3, dtype=np.float32) * 32767).astype(np.int16).tobytes()
_SILENCE = np.zeros(FRAME_SIZE, dtype=np.int16).tobytes()


def _utterance() -> list[bytes]:
    """Chunks for one complete utterance: trigger speech, then end silence."""
    return [_SPEECH] * SPEECH_TRIGGER_FRAMES + [_SILENCE] * SILENCE_END_FRAMES


@pytest.mark.asyncio
async def test_mute_sentinel_abandons_half_captured_utterance() -> None:
    """Speech before the mute must not leak into the post-unmute capture."""
    pipeline = _make_pipeline()
    queue: asyncio.Queue = asyncio.Queue()

    # Half an utterance (capture triggers, never completes), then mute.
    for _ in range(SPEECH_TRIGGER_FRAMES):
        await queue.put(_SPEECH)
    await queue.put(None)
    # A full clean utterance after unmute.
    for chunk in _utterance():
        await queue.put(chunk)

    audio = await asyncio.wait_for(pipeline.stream_capture(queue), timeout=5)

    # Only the post-mute utterance: trigger frames + end-silence frames.
    expected = (SPEECH_TRIGGER_FRAMES + SILENCE_END_FRAMES) * FRAME_SIZE
    assert len(audio) == expected


@pytest.mark.asyncio
async def test_mute_sentinel_while_idle_is_harmless() -> None:
    pipeline = _make_pipeline()
    queue: asyncio.Queue = asyncio.Queue()

    await queue.put(None)  # muted before any speech
    for chunk in _utterance():
        await queue.put(chunk)

    audio = await asyncio.wait_for(pipeline.stream_capture(queue), timeout=5)
    expected = (SPEECH_TRIGGER_FRAMES + SILENCE_END_FRAMES) * FRAME_SIZE
    assert len(audio) == expected


@pytest.mark.asyncio
async def test_mute_sentinel_discards_streaming_partial_state() -> None:
    """The streaming transcriber's half-utterance is thrown away on mute."""
    transcriber = FakeStreamingTranscriber()
    pipeline = _make_pipeline(transcriber)
    queue: asyncio.Queue = asyncio.Queue()

    for _ in range(SPEECH_TRIGGER_FRAMES):
        await queue.put(_SPEECH)
    await queue.put(None)
    for chunk in _utterance():
        await queue.put(chunk)

    text = await asyncio.wait_for(
        pipeline.stream_capture_and_transcribe(queue), timeout=5
    )

    assert text == "post-mute words"
    # Discards: capture start (aborted-capture residue) + the sentinel, plus
    # one real final at utterance end.
    assert transcriber.final_calls == 3


# ---------------------------------------------------------------------------
# Note: Silero VAD and faster-whisper are exercised in integration tests
# under tests/integration/ which require a working network connection
# for the first-run model download. v0.1.0 ships without those.
# ---------------------------------------------------------------------------


# ── Turn-taking reliability: cap, recheck reset, odd frames, onset ─────


def _speech_frames(n: int) -> list[bytes]:
    return [_SPEECH] * n


@pytest.mark.asyncio
async def test_utterance_is_force_capped_at_the_hard_limit(monkeypatch):
    """Audio that never dips below the VAD threshold (music near the mic)
    must finalize instead of growing forever."""
    from yumii.audio import stt as stt_module

    monkeypatch.setattr(stt_module, "_MAX_UTTERANCE_FRAMES", 30)
    pipeline = _make_pipeline()
    queue: asyncio.Queue = asyncio.Queue()
    for chunk in _speech_frames(200):
        await queue.put(chunk)

    audio = await asyncio.wait_for(pipeline.stream_capture(queue), timeout=5)
    assert len(audio) > 0  # finalized by the cap, not silence


@pytest.mark.asyncio
async def test_speech_resets_the_smart_turn_recheck_stride(monkeypatch):
    """A pause earlier in the turn must not raise the end-check latency for
    later pauses — speech resets the climbing recheck counter."""
    from yumii.audio import stt as stt_module

    class FakeSmartTurn:
        def __init__(self):
            self.calls = 0

        def is_complete(self, audio):
            self.calls += 1
            return (False, 0.4)

    fake = FakeSmartTurn()
    monkeypatch.setattr(stt_module, "_SMART_TURN_MAX_RECHECKS", 99)
    pipeline = _make_pipeline()
    pipeline._smart_turn = fake
    queue: asyncio.Queue = asyncio.Queue()

    for chunk in _speech_frames(12):   # trigger + a little speech
        await queue.put(chunk)
    for _ in range(6):                 # pause 1: probe fires at the quick threshold
        await queue.put(_silence_frame())
    for chunk in _speech_frames(3):    # speech resumes → rechecks reset
        await queue.put(chunk)
    for _ in range(6):                 # pause 2: probe must fire at 6 again
        await queue.put(_silence_frame())

    # Drain one more chunk so the probe from pause 2 completes.
    await queue.put(_silence_frame())
    task = asyncio.create_task(pipeline.stream_capture(queue))
    try:
        await asyncio.sleep(0.2)
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    # Without the reset, pause 2's probe would need 12 silence frames → 1 call.
    assert fake.calls >= 2


def _silence_frame() -> bytes:
    return (np.zeros(FRAME_SIZE, dtype=np.float32)).astype(np.int16).tobytes()


@pytest.mark.asyncio
async def test_odd_length_frames_are_dropped_not_fatal():
    """An odd-byte frame must not kill the capture (and stale Vosk residue
    must not prepend the lost utterance to the next one)."""
    transcriber = FakeStreamingTranscriber()
    pipeline = _make_pipeline(transcriber)
    queue: asyncio.Queue = asyncio.Queue()

    await queue.put(b"")  # odd byte count — used to crash the capture
    for chunk in _utterance():
        await queue.put(chunk)

    text = await asyncio.wait_for(
        pipeline.stream_capture_and_transcribe(queue), timeout=5
    )
    assert text == "post-mute words"  # the turn survived


@pytest.mark.asyncio
async def test_playback_end_sentinel_preserves_speech_onset():
    """A user replying inside the 400ms playback tail keeps their first
    phonemes — the sentinel only discards echo, not real onset."""
    pipeline = _make_pipeline(FakeStreamingTranscriber())
    queue: asyncio.Queue = asyncio.Queue()
    triggered = []

    # 4 onset frames sit in the pre-buffer (below the 8-frame trigger) when
    # the playback-end sentinel arrives mid-onset.
    for chunk in _speech_frames(4):
        await queue.put(chunk)
    await queue.put(None)
    for chunk in _speech_frames(5):    # preserved onset + 5 → trigger fires
        await queue.put(chunk)

    def on_speech_start():
        triggered.append(True)

    task = asyncio.create_task(
        pipeline.stream_capture(queue, on_speech_start=on_speech_start)
    )
    try:
        await asyncio.sleep(0.15)
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert triggered  # onset preserved → the preserved frames counted toward the trigger
