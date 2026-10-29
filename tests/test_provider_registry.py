"""The STT/TTS provider registry, and the drift it exists to prevent.

Before the registry, adding an ear meant editing five hand-kept lists, and
they drifted: vosk was selectable in the dashboard but missing from the
first-run download check. These tests make that class of bug a red build.
"""

import re
from pathlib import Path

import pytest

from yumii.core import providers

_INSTALLER = Path(__file__).resolve().parents[1] / "install.ps1"


@pytest.mark.parametrize("kind", ["stt", "tts"])
def test_ids_are_unique_and_labelled(kind):
    specs = providers.specs(kind)
    ids = [s.id.lower() for s in specs]
    assert ids and len(ids) == len(set(ids))
    assert all(s.label.strip() for s in specs)


@pytest.mark.parametrize("kind", ["stt", "tts"])
def test_every_provider_module_can_build(kind):
    import importlib

    for spec in providers.specs(kind):
        assert callable(getattr(importlib.import_module(spec.module), "build", None)), spec.id


def test_menu_order_is_stable():
    assert providers.ids("stt") == ["nemotron", "nemotron-multi", "moonshine", "local", "groq", "vosk"]
    assert providers.ids("tts") == ["Kokoro", "ElevenLabs", "CAMB.ai"]


def test_lookup_is_case_insensitive_and_unknown_falls_back():
    assert providers.get("tts", "kokoro").id == "Kokoro"
    assert providers.get("stt", "nope") is None
    assert providers.resolve("stt", "nope").id == "local"        # the old factory default
    assert providers.resolve("tts", "nope").id == "ElevenLabs"   # the old factory default


def test_duplicate_ids_are_rejected():
    with pytest.raises(ValueError, match="Duplicate"):
        providers.register("stt", "GROQ", __name__, label="again")


def test_dashboard_choices_are_the_registry():
    from yumii.api import server

    assert server._SETTING_CHOICES["STT_PROVIDER"] == providers.ids("stt")
    assert server._SETTING_CHOICES["TTS_PROVIDER"] == providers.ids("tts")


def test_provider_keys_are_allowed_in_auth_json():
    from yumii.core.credential_store import CREDENTIAL_KEYS

    assert providers.credential_keys() <= CREDENTIAL_KEYS


@pytest.mark.parametrize("var,kind", [("ears", "stt"), ("voice", "tts")])
def test_installer_menus_only_offer_registered_providers(var, kind):
    """install.ps1 runs before Python exists, so it can't import the registry —
    this keeps its hand-written menus honest instead."""
    match = re.search(rf"\${var} = @\(([^)]*)\)", _INSTALLER.read_text(encoding="utf-8"))
    assert match, f"install.ps1 lost its ${var} menu"
    offered = re.findall(r'"([^"]+)"', match.group(1))
    assert offered and set(offered) <= set(providers.ids(kind))


@pytest.mark.parametrize("kind,setting", [("stt", "stt_provider"), ("tts", "tts_provider")])
def test_every_local_model_is_covered_by_first_run(monkeypatch, kind, setting):
    """The vosk drift: a provider with a downloadable model must make
    needs_download() true when its model is missing."""
    import importlib

    from yumii.core import config, models

    for spec in providers.specs(kind):
        if not spec.downloads:
            continue
        other = "groq" if kind == "tts" else "ElevenLabs"  # cloud: nothing to download
        monkeypatch.setattr(config.settings, setting, spec.id)
        monkeypatch.setattr(config.settings, "stt_provider" if kind == "tts" else "tts_provider", other)
        module = importlib.import_module(spec.module)
        monkeypatch.setattr(module, "present", lambda s: False)
        assert models.needs_download() is True, spec.id
        monkeypatch.setattr(module, "present", lambda s: True)
        assert models.needs_download() is False, spec.id


@pytest.mark.parametrize("kind", ["stt", "tts"])
def test_factories_build_whatever_the_registry_resolves(monkeypatch, kind):
    import importlib

    from yumii.audio.stt_factory import get_stt_provider
    from yumii.core import config
    from yumii.tts.factory import get_speaker

    factory, setting = (get_stt_provider, "stt_provider") if kind == "stt" else (get_speaker, "tts_provider")
    for spec in providers.specs(kind):
        module = importlib.import_module(spec.module)
        monkeypatch.setattr(module, "build", lambda s: ("built", s.id))
        monkeypatch.setattr(config.settings, setting, spec.id)
        assert factory() == ("built", spec.id)


def test_nemotron_variants_share_one_module():
    en, multi = providers.get("stt", "nemotron"), providers.get("stt", "nemotron-multi")
    assert en.module == multi.module
    assert (en.options["variant"], multi.options["variant"]) == ("en", "multi")
