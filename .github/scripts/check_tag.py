#!/usr/bin/env python3
"""Fail if the pushed release tag does not match the project version.

check_versions.py keeps pyproject / tauri.conf / Cargo aligned with each
other — this keeps them aligned with the TAG being published. Without it,
tagging v0.14.0 over a pyproject still at 0.13.0 ships a release whose
installer installs the previous version. Runs in the release workflow's
test job; the tag name arrives via the TAG_NAME env var. Runnable locally:
``TAG_NAME=v0.14.0 python .github/scripts/check_tag.py``.
"""

from __future__ import annotations

import os
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    tag = os.environ.get("TAG_NAME", "").strip()
    if not tag:
        print("check_tag: TAG_NAME is not set — nothing to verify", file=sys.stderr)
        return 1

    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]["version"]

    expected = f"v{version}"
    if tag != expected:
        print(
            f"check_tag: tag {tag!r} does not match pyproject version {version!r} "
            f"(expected tag {expected!r}). Bump the versions, then tag.",
            file=sys.stderr,
        )
        return 1

    print(f"check_tag: tag {tag!r} matches pyproject {version!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
