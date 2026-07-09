#!/usr/bin/env python3
"""Fail if the product version differs across the files that declare it.

pyproject.toml (the Python package), tauri.conf.json (the desktop app
metadata), and Cargo.toml (the Rust shell) each carry their own version
string. They drifted once (0.9.0 vs 0.1.0), which would have shipped a
packaged app labelled v0.1.0. CI runs this so the release routine can't
silently forget one again. Runnable locally too: ``python
.github/scripts/check_versions.py``.
"""

from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load() -> dict[str, str]:
    pyproject = tomllib.loads(
        (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]["version"]
    tauri = json.loads(
        (ROOT / "desktop/src-tauri/tauri.conf.json").read_text(encoding="utf-8")
    )["version"]
    cargo = tomllib.loads(
        (ROOT / "desktop/src-tauri/Cargo.toml").read_text(encoding="utf-8")
    )["package"]["version"]
    return {
        "pyproject.toml": pyproject,
        "desktop/src-tauri/tauri.conf.json": tauri,
        "desktop/src-tauri/Cargo.toml": cargo,
    }


def main() -> int:
    versions = _load()
    if len(set(versions.values())) != 1:
        print("Version drift detected — these must all match:")
        for name, ver in versions.items():
            print(f"  {ver:<10} {name}")
        return 1
    print(f"All versions aligned: {next(iter(versions.values()))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
