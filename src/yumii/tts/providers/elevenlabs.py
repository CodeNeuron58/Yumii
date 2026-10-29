"""ElevenLabs — cloud voice, streamed as PCM."""

from __future__ import annotations

from yumii.core.providers import ProviderSpec, register

register("tts", "ElevenLabs", __name__, label="ElevenLabs (cloud)",
         credential_keys=("ELEVENLABS_API_KEY", "ELEVENLABS_VOICE_ID"))


def build(spec: ProviderSpec):
    from yumii.tts.speaker import YumiiSpeaker  # lazy: the elevenlabs SDK is heavy at import

    return YumiiSpeaker()
