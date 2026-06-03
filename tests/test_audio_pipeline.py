"""Tests for the audio pipeline's VAD-side logic.

These tests deliberately avoid loading the Silero VAD or faster-whisper
models (which require a working torch + network for the model download).
They exercise pure-Python helpers: the RMS energy gate and the PCM
normalization, which are deterministic.
"""

import numpy as np
import pytest

from yumi.audio.stt import float_to_pcm16, normalize_audio, rms_energy


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
# Note: Silero VAD and faster-whisper are exercised in integration tests
# under tests/integration/ which require a working network connection
# for the first-run model download. v0.1.0 ships without those.
# ---------------------------------------------------------------------------
