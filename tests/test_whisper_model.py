"""Tests for the GitHub-mirror Whisper downloader.

No real network: the zip download is faked with a local zip. Verifies
the completeness check (the partial-download bug), purge, and that an
incomplete archive raises instead of silently succeeding.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from yumii.audio import whisper_model as wm


@pytest.fixture
def isolated_models(tmp_path, monkeypatch):
    monkeypatch.setattr(wm, "_models_root", lambda: tmp_path / "whisper")
    return tmp_path / "whisper"


def _write_model(dir_: Path, files):
    dir_.mkdir(parents=True, exist_ok=True)
    for f in files:
        (dir_ / f).write_text("x")


# ── completeness (the exact clean-machine bug) ─────────────────────────


def test_incomplete_reads_as_absent(isolated_models):
    # model.bin + tokenizer landed, config.json didn't — must NOT count.
    _write_model(wm.model_dir_for("base"), ["model.bin", "tokenizer.json"])
    assert wm.is_present("base") is False


def test_complete_reads_as_present(isolated_models):
    _write_model(
        wm.model_dir_for("base"), ["config.json", "model.bin", "tokenizer.json"]
    )
    assert wm.is_present("base") is True


def test_missing_reads_as_absent(isolated_models):
    assert wm.is_present("base") is False


def test_purge_removes_the_model(isolated_models):
    _write_model(wm.model_dir_for("base"), ["config.json", "model.bin", "tokenizer.json"])
    assert wm.is_present("base") is True
    wm.purge("base")
    assert wm.is_present("base") is False


def test_unknown_size_falls_back_to_base(isolated_models):
    assert wm.model_dir_for("enormous").name == "base"


# ── download + extract ─────────────────────────────────────────────────


def _fake_zip(path: Path, files: dict[str, str]):
    with zipfile.ZipFile(path, "w") as z:
        for name, content in files.items():
            z.writestr(name, content)


def test_download_extracts_complete_model(isolated_models, monkeypatch, tmp_path):
    src_zip = tmp_path / "src.zip"
    _fake_zip(src_zip, {
        "config.json": "{}", "model.bin": "weights",
        "tokenizer.json": "{}", "vocabulary.txt": "words",
    })

    def fake_urlretrieve(url, out, reporthook=None):
        if reporthook:
            reporthook(1, 100, 100)  # 100%
        import shutil
        shutil.copy(src_zip, out)

    monkeypatch.setattr(wm.urllib.request, "urlretrieve", fake_urlretrieve)

    fracs: list[float] = []
    path = wm.get_whisper_model_dir("base", on_progress=fracs.append)

    assert Path(path) == wm.model_dir_for("base")
    assert wm.is_present("base") is True
    assert (wm.model_dir_for("base") / "config.json").exists()
    assert 1.0 in fracs  # real % progress


def test_incomplete_archive_raises_and_cleans(isolated_models, monkeypatch, tmp_path):
    # A zip missing config.json → must raise, not leave a broken model.
    src_zip = tmp_path / "bad.zip"
    _fake_zip(src_zip, {"model.bin": "weights", "tokenizer.json": "{}"})

    def fake_urlretrieve(url, out, reporthook=None):
        import shutil
        shutil.copy(src_zip, out)

    monkeypatch.setattr(wm.urllib.request, "urlretrieve", fake_urlretrieve)

    with pytest.raises(RuntimeError, match="incomplete"):
        wm.get_whisper_model_dir("base")
    assert wm.is_present("base") is False  # cleaned up, ready to retry


def test_present_model_skips_download(isolated_models, monkeypatch):
    _write_model(
        wm.model_dir_for("base"), ["config.json", "model.bin", "tokenizer.json"]
    )

    def boom(*a, **k):
        raise AssertionError("should not download when already present")

    monkeypatch.setattr(wm.urllib.request, "urlretrieve", boom)
    assert wm.get_whisper_model_dir("base") == str(wm.model_dir_for("base"))
