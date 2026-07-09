"""Tests for the ONNX Silero VAD (torch-free)."""

import sys
from pathlib import Path

import numpy as np

from yumii.audio.silero_vad import _MODEL_PATH, SileroVAD


def test_model_is_bundled_in_the_package():
    """The ~2MB ONNX must ship inside the package (no first-run download)."""
    assert Path(_MODEL_PATH).exists(), f"missing bundled model: {_MODEL_PATH}"
    assert Path(_MODEL_PATH).stat().st_size > 1_000_000


def test_vad_does_not_import_torch():
    SileroVAD()
    assert "torch" not in sys.modules


def test_silence_is_not_speech():
    vad = SileroVAD()
    vad.reset_states()
    silence = np.zeros(512, dtype=np.float32)
    for _ in range(30):
        assert vad(silence, 16000) < 0.5


def test_returns_probability_in_range():
    vad = SileroVAD()
    p = vad(np.random.randn(512).astype(np.float32) * 0.1, 16000)
    assert 0.0 <= p <= 1.0


def test_accepts_1d_and_2d_frames():
    vad = SileroVAD()
    frame_1d = np.zeros(512, dtype=np.float32)
    frame_2d = np.zeros((1, 512), dtype=np.float32)
    assert isinstance(vad(frame_1d, 16000), float)
    assert isinstance(vad(frame_2d, 16000), float)


def test_reset_clears_state_and_context():
    vad = SileroVAD()
    # push some non-zero audio so state/context become non-zero
    for _ in range(5):
        vad(np.random.randn(512).astype(np.float32) * 0.3, 16000)
    assert vad._context.any() or vad._state.any()
    vad.reset_states()
    assert not vad._context.any()
    assert not vad._state.any()
