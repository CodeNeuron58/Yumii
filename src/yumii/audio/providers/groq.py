"""Groq Whisper (whisper-large-v3-turbo) — fast cloud transcription, nothing to download."""

from __future__ import annotations

from yumii.core.config import settings
from yumii.core.providers import ProviderSpec, register

register("stt", "groq", __name__, label="Groq Whisper (cloud, fast)", credential_keys=("GROQ_API_KEY",))


def build(spec: ProviderSpec):
    from yumii.audio.stt_providers import GroqSTT

    return GroqSTT(api_key=settings.groq_api_key)
