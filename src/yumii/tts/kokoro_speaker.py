"""Kokoro local TTS provider for Yumii.

Runs Kokoro-82M fully offline via ONNX Runtime on CPU — no API key, no
cloud. Model files (~120 MB for the default int8 variant) are downloaded
to ``~/.yumii/models/kokoro`` on first use.

Output is 24 kHz signed 16-bit PCM, the same raw format the orb
frontend's streaming decoder expects, so chunks flow through the
engine's ``audio_chunk`` protocol unchanged.
"""

from __future__ import annotations

import base64
import io
import wave
from typing import Any, AsyncGenerator

import numpy as np

from yumii.core.config import settings
from yumii.core.interfaces import BaseSpeaker
from yumii.core.logging import get_logger
from yumii.tts.kokoro_model import get_kokoro_model_paths

log = get_logger(__name__)

DEFAULT_VOICE = "af_heart"


def _float32_to_pcm16_bytes(samples: np.ndarray) -> bytes:
    samples = np.clip(samples, -1.0, 1.0)
    return (samples * 32767).astype(np.int16).tobytes()


class KokoroSpeaker(BaseSpeaker):
    """Local TTS via kokoro-onnx (CPU, offline)."""

    def __init__(self) -> None:
        """Resolve (and if needed download) the model, then load it."""
        from kokoro_onnx import Kokoro
        from kokoro_onnx.config import SAMPLE_RATE

        model_path, voices_path = get_kokoro_model_paths(settings.kokoro_model_size)
        log.info("kokoro_loading", model=model_path)
        self.kokoro = Kokoro(model_path, voices_path)
        self.sample_rate = SAMPLE_RATE

        voice = (settings.kokoro_voice or DEFAULT_VOICE).strip()
        available = self.kokoro.get_voices()
        if voice not in available:
            log.warning("kokoro_unknown_voice_fallback", voice=voice, fallback=DEFAULT_VOICE)
            voice = DEFAULT_VOICE if DEFAULT_VOICE in available else available[0]
        self.voice = voice
        log.info("kokoro_ready", voice=self.voice, sample_rate=self.sample_rate)

    async def stream_speak(self, text: str) -> AsyncGenerator[Any, None]:
        """Yield metadata, then base64 PCM16 chunks as batches finish.

        ``create_stream`` synthesizes phoneme batches in a worker thread
        and yields each as soon as it's ready, so playback of the first
        batch starts while later ones are still being generated.
        """
        if not text or not text.strip():
            return

        yield {"type": "metadata", "sampleRate": self.sample_rate}

        try:
            async for samples, _sr in self.kokoro.create_stream(
                text, voice=self.voice, speed=1.0, lang="en-us"
            ):
                if samples is None or len(samples) == 0:
                    continue
                yield base64.b64encode(_float32_to_pcm16_bytes(samples)).decode("ascii")
        except Exception as e:
            log.error("kokoro_stream_error", error=str(e), exc_info=True)
            raise

    def speak(self, text: str, streaming: bool = False) -> tuple[str | None, float]:
        """Blocking synthesis returning base64 WAV (legacy non-streaming path).

        WAV (not raw PCM) because the frontend's legacy path decodes via
        ``decodeAudioData``, which needs a container.
        """
        if not text:
            return None, 0.0
        try:
            samples, sr = self.kokoro.create(
                text, voice=self.voice, speed=1.0, lang="en-us"
            )
            pcm = _float32_to_pcm16_bytes(samples)
            buf = io.BytesIO()
            with wave.open(buf, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sr)
                wf.writeframes(pcm)
            duration = len(samples) / sr
        except Exception as e:
            log.error("kokoro_tts_error", error=str(e), exc_info=True)
            return None, 0.0
        return base64.b64encode(buf.getvalue()).decode("ascii"), duration
