"""CAMB.ai — cloud voice."""

from __future__ import annotations

from yumii.core.providers import ProviderSpec, register

register("tts", "CAMB.ai", __name__, label="CAMB.ai (cloud)",
         credential_keys=("CAMB_API_KEY", "CAMB_VOICE_ID"))


def build(spec: ProviderSpec):
    from yumii.tts.camb_speaker import CambSpeaker

    return CambSpeaker()
