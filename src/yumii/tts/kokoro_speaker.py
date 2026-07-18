"""Kokoro-82M local TTS via ONNX (CPU, offline, no API key). Output: 24 kHz PCM16."""

from __future__ import annotations

import asyncio
import base64
import io
import re
import threading
import wave
from typing import Any, AsyncGenerator

import numpy as np

from yumii.core.config import settings
from yumii.core.interfaces import BaseSpeaker
from yumii.core.logging import get_logger
from yumii.tts.kokoro_model import get_kokoro_model_paths

log = get_logger(__name__)

DEFAULT_VOICE = "af_heart"

# Gap between separately-synthesized chunks so they don't run together.
_CHUNK_GAP_SEC = 0.08

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+")
_CLAUSE_SPLIT = re.compile(r"(?<=[,;:])\s+")
_CONJ_SPLIT = re.compile(r"\s+(?=(?:and|but|so|because|while|or|then)\b)", re.IGNORECASE)

# First chunk small (start fast); later chunks grow but stay ~1.4x delivered so playback doesn't outrun synthesis.
_FIRST_CHUNK_BUDGET = 48
_BUDGET_GROWTH = 1.4
_MIN_BUDGET = 60


def _atoms(text: str) -> list[str]:
    """Break text into sentences, then clauses, then run-on clauses at conjunctions."""
    out: list[str] = []
    for s in _SENTENCE_SPLIT.split(text.strip()):
        for c in _CLAUSE_SPLIT.split(s.strip()):
            c = c.strip()
            if not c:
                continue
            if len(c) > _MIN_BUDGET:
                out.extend(p.strip() for p in _CONJ_SPLIT.split(c) if p.strip())
            else:
                out.append(c)
    return out


def _split_speech_chunks(text: str) -> list[str]:
    """Pack atoms into chunks under a growing budget so speech starts fast without stalling."""
    atoms = _atoms(text)
    if not atoms:
        t = text.strip()
        return [t] if t else []

    chunks: list[str] = []
    budget = _FIRST_CHUNK_BUDGET
    delivered = 0
    cur = ""
    for atom in atoms:
        candidate = f"{cur} {atom}" if cur else atom
        if cur and len(candidate) > budget:
            chunks.append(cur)
            delivered += len(cur)
            budget = max(_MIN_BUDGET, int(_BUDGET_GROWTH * delivered))
            cur = atom
        else:
            cur = candidate
    if cur:
        chunks.append(cur)
    return chunks


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

        # Warm up in the background — the first ONNX run is ~30% slower.
        threading.Thread(target=self._warmup, daemon=True).start()

    def _warmup(self) -> None:
        try:
            self.kokoro.create("Hi.", voice=self.voice, speed=1.0, lang="en-us")
            log.debug("kokoro_warmed_up")
        except Exception as e:
            log.warning("kokoro_warmup_failed", error=str(e))

    async def stream_speak(self, text: str) -> AsyncGenerator[Any, None]:
        """Yield metadata, then base64 PCM16 chunks — one per sentence, so the first plays while the rest generate."""
        if not text or not text.strip():
            return

        yield {"type": "metadata", "sampleRate": self.sample_rate}

        gap = np.zeros(int(_CHUNK_GAP_SEC * self.sample_rate), dtype=np.float32)
        try:
            for i, chunk_text in enumerate(_split_speech_chunks(text)):
                samples, _sr = await asyncio.to_thread(
                    self.kokoro.create,
                    chunk_text,
                    voice=self.voice,
                    speed=1.0,
                    lang="en-us",
                )
                if samples is None or len(samples) == 0:
                    continue
                if i > 0:
                    samples = np.concatenate([gap, samples])
                yield base64.b64encode(_float32_to_pcm16_bytes(samples)).decode("ascii")
        except Exception as e:
            log.error("kokoro_stream_error", error=str(e), exc_info=True)
            raise

    def speak(self, text: str, streaming: bool = False) -> tuple[str | None, float]:
        """Blocking synthesis returning base64 WAV (legacy non-streaming path; WAV needs a container)."""
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
