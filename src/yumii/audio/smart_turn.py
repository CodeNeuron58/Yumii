"""Smart Turn v3 (pipecat-ai, BSD-2-Clause): end-of-turn detection from raw audio.

A Whisper-tiny backbone (~8M params, int8 ONNX, ~9 MB) with a linear
classifier that decides whether the user finished their thought — using
prosody, not just silence. It runs alongside Silero VAD: when VAD reports a
brief silence, the whole user turn is fed to the model; "incomplete" keeps
listening (the user paused mid-sentence), "complete" closes the turn fast.

Inference mirrors pipecat-ai/smart-turn's ``inference.py``: 16 kHz mono PCM
float32, kept to the last 8 seconds (left-zero-padded if shorter), through a
Whisper log-mel feature extractor (numpy-only; mel filters ship inside
``transformers`` — no torch, no network), then the ONNX session returns the
completion probability directly.

The weights live on Hugging Face; this project mirrors downloads off GitHub
releases where the HF CDN is unreachable. Point ``YUMII_SMART_TURN_URL`` at a
mirror to override the source.
"""

from __future__ import annotations

import os
import urllib.request
from pathlib import Path
from typing import Callable

import numpy as np
from yumii.core.logging import get_logger

log = get_logger(__name__)

_MODEL_FILE = "smart-turn-v3.2-cpu.onnx"
_MODEL_URL = (
    "https://huggingface.co/pipecat-ai/smart-turn-v3/resolve/main/" + _MODEL_FILE
)
_SAMPLE_RATE = 16000
_MAX_SECONDS = 8
_MAX_SAMPLES = _MAX_SECONDS * _SAMPLE_RATE

ProgressFn = Callable[[float], None]


def _models_dir() -> Path:
    d = Path.home() / ".yumii" / "models" / "smart-turn"
    d.mkdir(parents=True, exist_ok=True)
    return d


def model_path() -> Path:
    return _models_dir() / _MODEL_FILE


def is_present() -> bool:
    return model_path().exists()


def _download(target: Path, on_progress: ProgressFn | None) -> None:
    """Fetch the model atomically (.part rename) with hard timeouts so an
    unreachable mirror can't hang boot."""
    url = os.environ.get("YUMII_SMART_TURN_URL") or _MODEL_URL
    part = target.with_suffix(target.suffix + ".part")
    log.info("downloading_smart_turn", url=url, target=str(target))

    request = urllib.request.Request(url, headers={"User-Agent": "yumii"})
    with urllib.request.urlopen(request, timeout=30) as resp, open(part, "wb") as f:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        while True:
            block = resp.read(1 << 16)
            if not block:
                break
            f.write(block)
            done += len(block)
            if on_progress is not None and total:
                on_progress(min(1.0, done / total))
    os.replace(str(part), str(target))


def prefetch(on_progress: ProgressFn | None = None) -> Path:
    """Ensure the model file exists; returns its path. Raises on download failure."""
    path = model_path()
    if not path.exists():
        _download(path, on_progress)
    return path


def truncate_or_pad_to_last_n_seconds(audio: np.ndarray, n_seconds: int = 8) -> np.ndarray:
    """Keep the final ``n_seconds``; left-pad zeros so the speech sits at the end."""
    max_samples = n_seconds * _SAMPLE_RATE
    if len(audio) > max_samples:
        return audio[-max_samples:]
    if len(audio) < max_samples:
        return np.concatenate([np.zeros(max_samples - len(audio), dtype=audio.dtype), audio])
    return audio


class SmartTurn:
    """ONNX end-of-turn classifier over 16 kHz mono float32 audio."""

    def __init__(self, path: str | Path | None = None) -> None:
        import onnxruntime as ort

        resolved = str(path) if path else str(prefetch())
        log.info("smart_turn_loading", model=resolved)

        options = ort.SessionOptions()
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        options.inter_op_num_threads = 1
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self._session = ort.InferenceSession(resolved, sess_options=options)

        # Lazy import: pulls transformers only when the model is actually used.
        from transformers import WhisperFeatureExtractor

        self._feature_extractor = WhisperFeatureExtractor(chunk_length=_MAX_SECONDS)
        log.info("smart_turn_ready")

    def predict(self, audio: np.ndarray) -> float:
        """Return the probability (0..1) that the user's turn is complete."""
        clipped = np.clip(np.asarray(audio, dtype=np.float32), -1.0, 1.0)
        clipped = truncate_or_pad_to_last_n_seconds(clipped, _MAX_SECONDS)

        inputs = self._feature_extractor(
            clipped,
            sampling_rate=_SAMPLE_RATE,
            return_tensors="np",
            padding="max_length",
            max_length=_MAX_SAMPLES,
            truncation=True,
            do_normalize=True,
        )
        features = inputs.input_features.squeeze(0).astype(np.float32)
        features = np.expand_dims(features, axis=0)

        outputs = self._session.run(None, {"input_features": features})
        return float(outputs[0][0].item())

    def is_complete(self, audio: np.ndarray) -> tuple[bool, float]:
        prob = self.predict(audio)
        return prob > 0.5, prob


def get_smart_turn() -> SmartTurn | None:
    """Load Smart Turn, or ``None`` if it can't be built (feature quietly disables)."""
    try:
        return SmartTurn()
    except Exception as e:
        log.warning("smart_turn_unavailable", error=str(e))
        return None
