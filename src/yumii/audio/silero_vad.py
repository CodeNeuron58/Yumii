"""Silero VAD on ONNX Runtime — no torch.

Silero VAD used to load via ``torch.hub.load("snakers4/silero-vad")``,
which dragged in torch + torchaudio (hundreds of MB) for one small RNN
and downloaded the weights from GitHub at first run. This wrapper runs
the same v5 model on onnxruntime (already a dependency via Kokoro) from
a ~2 MB file bundled in the package — no torch, no first-run download.

The model is stateful (an RNN): each call takes the previous hidden
state and returns the next one. ``reset_states`` zeroes it at the start
of every capture, exactly like the torch model's ``reset_states``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import onnxruntime as ort

from yumii.core.logging import get_logger

log = get_logger(__name__)

# Bundled in the wheel (assets/ is package data). __file__ = audio/silero_vad.py
_MODEL_PATH = Path(__file__).parent.parent / "assets" / "models" / "silero_vad.onnx"

# v5 hidden state shape: [2, batch, 128].
_STATE_SHAPE = (2, 1, 128)
# v5 prepends a 64-sample context (the tail of the previous frame) to
# each 512-sample frame at 16 kHz — the model is fed 576 samples. The
# official OnnxWrapper does this internally; without it the model sees
# malformed input and returns ~0 for everything.
_CONTEXT_SIZE = 64


class SileroVAD:
    """Voice-activity detector wrapping the Silero v5 ONNX model.

    Drop-in for the old torch model's usage in the audio pipeline:
    ``reset_states()`` then ``prob = vad(frame, sr)`` per 512-sample
    frame at 16 kHz.
    """

    def __init__(self, model_path: str | Path = _MODEL_PATH) -> None:
        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1
        opts.log_severity_level = 3  # quiet
        self._session = ort.InferenceSession(
            str(model_path), sess_options=opts, providers=["CPUExecutionProvider"]
        )
        self._state = np.zeros(_STATE_SHAPE, dtype=np.float32)
        self._context = np.zeros((1, _CONTEXT_SIZE), dtype=np.float32)
        log.info("silero_vad_ready", backend="onnxruntime")

    def reset_states(self) -> None:
        """Clear the RNN hidden state + context (call before each capture)."""
        self._state = np.zeros(_STATE_SHAPE, dtype=np.float32)
        self._context = np.zeros((1, _CONTEXT_SIZE), dtype=np.float32)

    def __call__(self, frame: np.ndarray, sr: int) -> float:
        """Return the speech probability for one audio frame.

        Args:
            frame: 1-D float32 samples (512 at 16 kHz). A 2-D
                ``[1, n]`` array is accepted too.
            sr: Sample rate (16000).
        """
        x = np.asarray(frame, dtype=np.float32)
        if x.ndim == 1:
            x = x[np.newaxis, :]
        # Prepend the previous frame's tail; feed 64 + 512 = 576 samples.
        x = np.concatenate([self._context, x], axis=1)
        out, self._state = self._session.run(
            None,
            {
                "input": x,
                "state": self._state,
                "sr": np.array(sr, dtype=np.int64),
            },
        )
        # Context for the next call is the tail of what we just fed.
        self._context = x[:, -_CONTEXT_SIZE:]
        return float(out[0, 0])
