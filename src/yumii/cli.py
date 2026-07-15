# -*- coding: utf-8 -*-
"""Yumii backend launcher.

Yumii is a desktop application — the interactive CLI, setup wizards,
and browser mode were retired with the desktop pivot (they live on in
the ``cli-launch`` branch). This module exists so the desktop shell
(and developers) can start the backend:

    yumii server            # start the FastAPI backend (headless)
    python -m yumii server  # same — what the desktop shell launches

To actually meet Yumii, run the desktop app:

    cd desktop && npx @tauri-apps/cli dev
"""

from __future__ import annotations

import os
import sys

from yumii.core.logging import configure_logging

try:
    from importlib.metadata import version as _pkg_version

    VERSION = _pkg_version("yumii")
except Exception:
    VERSION = "0.0.0-dev"

_USAGE = f"""Yumii {VERSION} — an AI companion for your desktop.

Yumii runs as a desktop application; this command only hosts her backend.

  yumii server     start the backend (the desktop app does this for you)
  yumii --version  print the version

Development: run the app with  cd desktop && npx @tauri-apps/cli dev
"""


def _run_server() -> None:
    """Boot the FastAPI backend on 127.0.0.1:8000 (blocking)."""
    # onnxruntime/numpy can trip over duplicate OpenMP runtimes on
    # Windows; the desktop shell sets this too, but direct runs need it.
    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
    configure_logging()

    import uvicorn

    from yumii.api.server import app as fastapi_app

    uvicorn.run(fastapi_app, host="127.0.0.1", port=8000, log_config=None)


def main() -> None:
    """Console entry point (``yumii`` command / ``python -m yumii``)."""
    args = sys.argv[1:]

    if not args:
        print(_USAGE)
        return
    if args[0] in ("--version", "-V", "version"):
        print(f"yumii {VERSION}")
        return
    if args[0] == "server":
        _run_server()
        return

    print(f"Unknown command: {args[0]!r}\n")
    print(_USAGE)
    sys.exit(2)


if __name__ == "__main__":
    main()
