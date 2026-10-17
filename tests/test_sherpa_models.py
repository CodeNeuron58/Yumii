"""sherpa-onnx providers against REAL contracts, not just fakes.

The provider tests (test_moonshine_stt / test_nemotron_stt) use fake
recognizers, which is why two release-blocking bugs slipped past them:
- the native runtime segfaulted on Windows (sherpa-onnx-core missing, so
  sherpa bound a stale System32 onnxruntime.dll), and
- Moonshine's completeness check named v1 files while the provider opens
  the v2 layout, so every good download was purged and re-fetched forever.
These tests pin both: one builds a real sherpa ONNX session in a subprocess
(a native crash fails the test instead of killing pytest), the rest tie each
model's _REQUIRED_FILES to the exact files its provider opens.
"""

import io
import subprocess
import sys
import tarfile
import types
from pathlib import Path

import pytest

from yumii.audio import moonshine_model, nemotron_model
from yumii.audio.stt_providers import MoonshineStreamingSTT, NemotronStreamingSTT

_VAD_ONNX = Path(__file__).resolve().parents[1] / "src" / "yumii" / "assets" / "models" / "silero_vad.onnx"


def test_sherpa_native_runtime_builds_a_session():
    code = (
        "import sys, sherpa_onnx\n"
        "cfg = sherpa_onnx.VadModelConfig()\n"
        "cfg.silero_vad.model = sys.argv[1]\n"
        "cfg.sample_rate = 16000\n"
        "sherpa_onnx.VoiceActivityDetector(cfg, buffer_size_in_seconds=5)\n"
        "print('ok')\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code, str(_VAD_ONNX)],
        capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0 and "ok" in proc.stdout, (
        f"sherpa-onnx native session failed (exit {proc.returncode}): {proc.stderr[-800:]}"
    )


def _fake_sherpa(captured: dict) -> types.ModuleType:
    """A sherpa_onnx stand-in that records which files a provider opens."""

    def _record(**kwargs):
        captured.update(kwargs)
        return object()

    mod = types.ModuleType("sherpa_onnx")
    mod.OfflineRecognizer = types.SimpleNamespace(from_moonshine_v2=_record)
    mod.OnlineRecognizer = types.SimpleNamespace(from_transducer=_record)
    return mod


def _opened_files(captured: dict) -> set[str]:
    return {Path(v).name for v in captured.values() if isinstance(v, str) and ("/" in v or "\\" in v)}


def test_moonshine_required_files_are_what_the_provider_opens(monkeypatch, tmp_path):
    captured: dict = {}
    monkeypatch.setitem(sys.modules, "sherpa_onnx", _fake_sherpa(captured))
    MoonshineStreamingSTT(str(tmp_path))
    assert _opened_files(captured) == set(moonshine_model._REQUIRED_FILES)


def test_nemotron_required_files_are_what_the_provider_opens(monkeypatch, tmp_path):
    captured: dict = {}
    monkeypatch.setitem(sys.modules, "sherpa_onnx", _fake_sherpa(captured))
    NemotronStreamingSTT(str(tmp_path))
    assert _opened_files(captured) == set(nemotron_model._REQUIRED_FILES)


def _write_archive(path: Path, top: str, files: tuple[str, ...]) -> None:
    with tarfile.open(path, "w:bz2") as tf:
        for name in files:
            data = b"x"
            info = tarfile.TarInfo(f"{top}/{name}")
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))


def test_moonshine_ensure_accepts_a_complete_download(monkeypatch, tmp_path):
    monkeypatch.setattr(moonshine_model, "_models_root", lambda: tmp_path)
    downloads = []

    def fake_download(url, dest, progress=None):
        downloads.append(url)
        _write_archive(Path(dest), moonshine_model._ARCHIVE_NAME, moonshine_model._REQUIRED_FILES)

    monkeypatch.setattr(moonshine_model, "download_file", fake_download)

    first = moonshine_model.ensure()
    second = moonshine_model.ensure()  # already present: no re-download

    assert first == second == str(tmp_path / moonshine_model._ARCHIVE_NAME)
    assert len(downloads) == 1
    assert not list(tmp_path.glob("*.tar.bz2"))  # archive cleaned up


def test_moonshine_ensure_rejects_an_incomplete_download(monkeypatch, tmp_path):
    monkeypatch.setattr(moonshine_model, "_models_root", lambda: tmp_path)
    monkeypatch.setattr(
        moonshine_model, "download_file",
        lambda url, dest, progress=None: _write_archive(
            Path(dest), moonshine_model._ARCHIVE_NAME, ("tokens.txt",)
        ),
    )
    with pytest.raises(RuntimeError, match="incomplete"):
        moonshine_model.ensure()
    assert not (tmp_path / moonshine_model._ARCHIVE_NAME).exists()  # partial purged
