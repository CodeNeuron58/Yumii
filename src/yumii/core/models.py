"""Download local STT + TTS models on first launch (VAD is bundled; only the LLM is cloud).

Which models exist, whether they're on disk, and how to fetch them is each
provider's own business (yumii.core.providers): this module just asks the
configured voice and ears, in that order.
"""

from __future__ import annotations

from typing import Any, Callable

from yumii.core import providers
from yumii.core.config import settings
from yumii.core.logging import get_logger

log = get_logger(__name__)

# on_progress(stage_label, fraction); fraction is 0..1 or None for indeterminate.
ProgressCb = Callable[[str, "float | None"], None]


def _selected() -> list[providers.ProviderSpec]:
    """The configured voice, then ears — the first-run download order."""
    return [
        providers.resolve("tts", settings.tts_provider),
        providers.resolve("stt", settings.stt_provider),
    ]


def needs_download() -> bool:
    """True if the configured voice or ears keep a local model that isn't complete on disk."""
    return any(not spec.present() for spec in _selected())


def _prefetch_smart_turn(report: Any) -> None:
    """Best-effort: Smart Turn is optional, so never fail boot over it."""
    try:
        from yumii.audio.smart_turn import is_present, prefetch

        if is_present():
            return
        report("Tuning her listening", 0.0)
        prefetch(on_progress=lambda f: report("Tuning her listening", f))
        log.info("smart_turn_prefetched")
    except Exception as e:
        log.warning("smart_turn_prefetch_failed", error=str(e))


def ensure_models_ready(on_progress: ProgressCb | None = None) -> None:
    """Download any missing local models. Blocking — call in a thread; raises on failure."""

    def report(stage: str, frac: float | None = None) -> None:
        if on_progress is None:
            return
        try:
            on_progress(stage, frac)
        except Exception:
            pass

    _prefetch_smart_turn(report)

    for spec in _selected():
        if not spec.present():
            spec.provision(report)

    report("ready", 1.0)
