"""Provider registry: the ears (STT) and voices (TTS) Yumii can wire.

The LLM side already works this way (``model_catalog.PROVIDER_WIRING``);
this finishes the pattern for speech. Every provider is ONE module that
registers itself at import and exposes up to three hooks:

    build(spec)            -> the provider instance (heavy SDKs imported here, lazily)
    present(spec)          -> True when its local model is complete on disk (omit: nothing to download)
    provision(spec, report)-> download/verify the model, reporting progress (omit: nothing to download)

    register("stt", "groq", __name__, label="Groq Whisper (cloud, fast)",
             credential_keys=("GROQ_API_KEY",))

The factories, first-run model downloads, the dashboard's choice lists and
labels all derive from here — adding a provider is one file plus one import
line in its package ``__init__``. Hooks are looked up on the module at call
time, so tests can monkeypatch a provider module's ``present``/``provision``.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from typing import Any, Callable

ProgressReport = Callable[[str, "float | None"], None]

# Unknown or legacy config values fall back to these (the factories' old defaults).
_DEFAULTS = {"stt": "local", "tts": "ElevenLabs"}
# Importing these packages registers every built-in provider, in menu order.
_PACKAGES = {"stt": "yumii.audio.providers", "tts": "yumii.tts.providers"}

_REGISTRY: dict[str, dict[str, "ProviderSpec"]] = {"stt": {}, "tts": {}}


@dataclass(frozen=True)
class ProviderSpec:
    """One registered provider: identity + metadata + where its hooks live."""

    kind: str  # "stt" | "tts"
    id: str  # the config value (STT_PROVIDER / TTS_PROVIDER), display case kept
    label: str  # human label for menus
    module: str  # dotted path of the module holding build/present/provision
    credential_keys: tuple[str, ...] = ()
    options: dict[str, Any] = field(default_factory=dict, hash=False, compare=False)

    def _hook(self, name: str) -> Callable[..., Any] | None:
        return getattr(importlib.import_module(self.module), name, None)

    @property
    def downloads(self) -> bool:
        """True if this provider keeps a local model that may need downloading."""
        return self._hook("provision") is not None

    def build(self) -> Any:
        return self._hook("build")(self)

    def present(self) -> bool:
        hook = self._hook("present")
        return True if hook is None else bool(hook(self))

    def provision(self, report: ProgressReport) -> None:
        hook = self._hook("provision")
        if hook is not None:
            hook(self, report)


def register(
    kind: str,
    provider_id: str,
    module: str,
    *,
    label: str,
    credential_keys: tuple[str, ...] = (),
    **options: Any,
) -> ProviderSpec:
    """Register a provider; ids are unique per kind (case-insensitively)."""
    if kind not in _REGISTRY:
        raise ValueError(f"Unknown provider kind: {kind!r}")
    if any(existing.lower() == provider_id.lower() for existing in _REGISTRY[kind]):
        raise ValueError(f"Duplicate {kind} provider id: {provider_id!r}")
    spec = ProviderSpec(kind, provider_id, label, module, tuple(credential_keys), dict(options))
    _REGISTRY[kind][provider_id] = spec
    return spec


def _load(kind: str) -> dict[str, ProviderSpec]:
    importlib.import_module(_PACKAGES[kind])
    return _REGISTRY[kind]


def specs(kind: str) -> list[ProviderSpec]:
    """Every registered provider of a kind, in menu order."""
    return list(_load(kind).values())


def ids(kind: str) -> list[str]:
    return [s.id for s in specs(kind)]


def labels(kind: str) -> dict[str, str]:
    return {s.id: s.label for s in specs(kind)}


def get(kind: str, provider_id: str | None) -> ProviderSpec | None:
    """Case-insensitive lookup ("Kokoro" == "kokoro"); None if unregistered."""
    wanted = (provider_id or "").strip().lower()
    return next((s for s in specs(kind) if s.id.lower() == wanted), None)


def resolve(kind: str, provider_id: str | None) -> ProviderSpec:
    """The provider to run for a config value — unknown values get the default."""
    return get(kind, provider_id) or get(kind, _DEFAULTS[kind])


def credential_keys() -> set[str]:
    """Every auth.json key some speech provider needs."""
    return {k for kind in _REGISTRY for s in specs(kind) for k in s.credential_keys}
