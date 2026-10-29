"""Vosk — offline streaming with word-by-word partials, the lightest local ear."""

from __future__ import annotations

from yumii.core.config import settings
from yumii.core.logging import get_logger
from yumii.core.providers import ProgressReport, ProviderSpec, register

log = get_logger(__name__)

register("stt", "vosk", __name__, label="Vosk (offline streaming, lightest)")


def build(spec: ProviderSpec):
    from yumii.audio.vosk_model import get_vosk_model_path
    from yumii.audio.vosk_provider import VoskSTT

    return VoskSTT(model_path=get_vosk_model_path(settings.vosk_model_size))


def present(spec: ProviderSpec) -> bool:
    from yumii.audio.vosk_model import is_present

    return is_present(settings.vosk_model_size)


def provision(spec: ProviderSpec, report: ProgressReport) -> None:
    from yumii.audio.vosk_model import get_vosk_model_path

    report("Getting her ears ready", None)  # the zip download reports no percentage
    get_vosk_model_path(settings.vosk_model_size)
    log.info("vosk_prefetched", size=settings.vosk_model_size)
