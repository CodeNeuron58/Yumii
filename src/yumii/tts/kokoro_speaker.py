"""Kokoro-82M local TTS via ONNX (CPU, offline, no API key). Output: 24 kHz PCM16."""

from __future__ import annotations

import asyncio
import base64
import io
import re
import threading
import time
import wave
from typing import Any, AsyncGenerator

import numpy as np

from yumii.core.config import settings
from yumii.core.interfaces import BaseSpeaker
from yumii.core.logging import get_logger
from yumii.tts.kokoro_model import get_kokoro_model_paths

log = get_logger(__name__)

DEFAULT_VOICE = "af_heart"

# Pause between separately-synthesized chunks — each is silence-trimmed, so
# without a little gap words on the boundary glue together. Kept small; the
# prefetch worker (see stream_speak) makes long gaps unnecessary.
_CHUNK_GAP_SEC = 0.04

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+")
_CLAUSE_SPLIT = re.compile(r"(?<=[,;:])\s+")
_CONJ_SPLIT = re.compile(r"\s+(?=(?:and|but|so|because|while|or|then)\b)", re.IGNORECASE)

# Chunk sizing. The prefetch worker keeps synthesis ahead of playback, so
# budgets exist for latency and interrupt-responsiveness only: a small first
# chunk starts the voice fast; steady chunks stay short enough that an
# in-flight synthesis never outlives a barge-in by long.
_FIRST_CHUNK_BUDGET = 32  # chars — ~1s of speech
_STEADY_BUDGET = 96       # chars — ~6s of audio


def _atoms(text: str) -> list[str]:
    """Break text into sentences, then clauses, then run-on clauses at conjunctions."""
    out: list[str] = []
    for s in _SENTENCE_SPLIT.split(text.strip()):
        for c in _CLAUSE_SPLIT.split(s.strip()):
            c = c.strip()
            if not c:
                continue
            if len(c) > _STEADY_BUDGET:
                out.extend(p.strip() for p in _CONJ_SPLIT.split(c) if p.strip())
            else:
                out.append(c)
    return out


def _split_speech_chunks(text: str) -> list[str]:
    """Pack atoms into chunks: small opener, then steady-size chunks."""
    atoms = _atoms(text)
    if not atoms:
        t = text.strip()
        return [t] if t else []

    chunks: list[str] = []
    cur = ""
    budget = _FIRST_CHUNK_BUDGET
    for atom in atoms:
        candidate = f"{cur} {atom}" if cur else atom
        if cur and len(candidate) > budget:
            chunks.append(cur)
            budget = _STEADY_BUDGET
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
        """Yield metadata, then base64 PCM16 chunks.

        Synthesis runs in a worker task that prefetches into a small bounded
        queue: the next chunk is always generating while the current one plays,
        instead of only starting after the consumer asks for it. Playback can
        then only stall if *average* synthesis RTF exceeds 1.0 (measured
        0.72–0.85 on the target CPU class, versus the old serial design that
        needed per-chunk RTF < 0.71 — the source of the mid-reply stalls).
        """
        if not text or not text.strip():
            return

        chunk_texts = _split_speech_chunks(text)
        if not chunk_texts:
            return

        gap = np.zeros(int(_CHUNK_GAP_SEC * self.sample_rate), dtype=np.float32)
        # Bounded: caps memory and keeps a ~2-chunk playback cushion.
        out: asyncio.Queue[Any] = asyncio.Queue(maxsize=2)

        async def _synth_worker() -> None:
            try:
                for i, chunk_text in enumerate(chunk_texts):
                    t0 = time.perf_counter()
                    samples, _sr = await asyncio.to_thread(
                        self.kokoro.create,
                        chunk_text,
                        voice=self.voice,
                        speed=1.0,
                        lang="en-us",
                    )
                    synth_sec = time.perf_counter() - t0
                    if samples is None or len(samples) == 0:
                        continue
                    audio_sec = len(samples) / self.sample_rate
                    log.debug(
                        "kokoro_chunk",
                        chars=len(chunk_text),
                        synth=round(synth_sec, 2),
                        audio=round(audio_sec, 2),
                        rtf=round(synth_sec / audio_sec, 2) if audio_sec else None,
                    )
                    if i > 0:
                        samples = np.concatenate([gap, samples])
                    await out.put(
                        base64.b64encode(_float32_to_pcm16_bytes(samples)).decode("ascii")
                    )
            except Exception as e:
                log.error("kokoro_stream_error", error=str(e), exc_info=True)
                await out.put(e)
            finally:
                await out.put(None)

        # Start the worker BEFORE the metadata yield: an async generator's body
        # only runs when the consumer pulls, so a task created below the yield
        # wouldn't begin synthesizing until the next pull — losing the whole
        # point of prefetching (the metadata consumer is busy broadcasting).
        worker = asyncio.create_task(_synth_worker())
        try:
            yield {"type": "metadata", "sampleRate": self.sample_rate}
            while True:
                item = await out.get()
                if item is None:
                    break
                if isinstance(item, Exception):
                    raise item
                yield item
        finally:
            # A consumer that breaks early (barge-in) must stop the worker, or
            # synthesis keeps burning CPU for audio nobody will play.
            worker.cancel()

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
