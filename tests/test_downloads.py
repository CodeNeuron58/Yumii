"""The shared downloader: atomic .part rename, bounded reads, truncation guard."""

import asyncio
from pathlib import Path

import pytest

from yumii.core.downloads import download_file


def _source(tmp_path: Path, name: str, payload: bytes) -> str:
    src = tmp_path / name
    src.write_bytes(payload)
    return src.as_uri()  # file:// — urlopen handles it, no network


@pytest.mark.asyncio
async def test_download_writes_atomically_and_reports_progress(tmp_path):
    payload = b"x" * (256 * 1024 + 7)  # spans multiple read blocks
    src = _source(tmp_path, "src.bin", payload)
    dest = tmp_path / "out" / "model.bin"

    fractions: list[float] = []
    await asyncio.to_thread(download_file, src, dest, fractions.append)

    assert dest.read_bytes() == payload
    assert not (dest.parent / "model.bin.part").exists()  # .part consumed
    assert fractions and fractions[-1] == 1.0             # progress reported


@pytest.mark.asyncio
async def test_failed_download_leaves_no_part_file(tmp_path):
    dest = tmp_path / "out" / "model.bin"

    with pytest.raises(Exception):
        await asyncio.to_thread(
            download_file, tmp_path.as_uri() + "/missing-model.bin", dest
        )

    assert not dest.exists()
    assert not (dest.parent / "model.bin.part").exists()
