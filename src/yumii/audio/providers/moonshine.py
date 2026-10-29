"""Moonshine v2 via sherpa-onnx — the lightweight local ear for weak hardware."""

from __future__ import annotations

from yumii.core.logging import get_logger
from yumii.core.providers import ProgressReport, ProviderSpec, register

log = get_logger(__name__)

register("stt", "moonshine", __name__, label="Moonshine v2 (local, lightweight)")


def build(spec: ProviderSpec):
    from yumii.audio.moonshine_model import get_moonshine_model_dir
    from yumii.audio.stt_providers import MoonshineStreamingSTT

    return MoonshineStreamingSTT(model_dir=get_moonshine_model_dir())


def present(spec: ProviderSpec) -> bool:
    from yumii.audio.moonshine_model import is_present

    return is_present()


def provision(spec: ProviderSpec, report: ProgressReport) -> None:
    from yumii.audio.moonshine_model import ensure

    stage = "Getting her ears ready"
    report(stage, 0.0)
    ensure(on_progress=lambda f: report(stage, f))
    log.info("moonshine_prefetched")
