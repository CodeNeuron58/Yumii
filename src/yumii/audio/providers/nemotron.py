"""NVIDIA Nemotron Speech Streaming via sherpa-onnx — true streaming, on-device."""

from __future__ import annotations

from yumii.core.logging import get_logger
from yumii.core.providers import ProgressReport, ProviderSpec, register

log = get_logger(__name__)

register("stt", "nemotron", __name__,
         label="NVIDIA Nemotron Speech (local streaming, English)", variant="en")
register("stt", "nemotron-multi", __name__,
         label="NVIDIA Nemotron 3.5 ASR (local streaming, multilingual)", variant="multi")


def build(spec: ProviderSpec):
    from yumii.audio.nemotron_model import get_nemotron_model_dir
    from yumii.audio.stt_providers import NemotronStreamingSTT

    # get_nemotron_model_dir() downloads if missing (self-healing) — first
    # launch normally prefetches it via provision() with progress.
    return NemotronStreamingSTT(model_dir=get_nemotron_model_dir(spec.options["variant"]))


def present(spec: ProviderSpec) -> bool:
    from yumii.audio.nemotron_model import is_present

    return is_present(spec.options["variant"])


def provision(spec: ProviderSpec, report: ProgressReport) -> None:
    from yumii.audio.nemotron_model import ensure

    stage = "Getting her ears ready"
    report(stage, 0.0)
    ensure(spec.options["variant"], on_progress=lambda f: report(stage, f))
    log.info("nemotron_prefetched", variant=spec.options["variant"])
