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
    # One discard on the sentinel + one real final at utterance end.
    assert transcriber.final_calls == 2


# ---------------------------------------------------------------------------
# Note: Silero VAD and faster-whisper are exercised in integration tests
# under tests/integration/ which require a working network connection
# for the first-run model download. v0.1.0 ships without those.
# ---------------------------------------------------------------------------
