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


# Loopback range the backend binds within. It prefers 8000; if that's
# taken (a dev server, another Yumii), it walks up until it finds a free
# port instead of dying — the orb probes the same range to find it, and
# the chosen port is written to the file below so the shell can open the
# dashboard on the right one.
_PORT_BASE = 8000
_PORT_TRIES = 12


def _pick_free_port() -> int:
    """Return the first free loopback port at or above 8000."""
    import socket

    for port in range(_PORT_BASE, _PORT_BASE + _PORT_TRIES):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(("127.0.0.1", port))
            return port
        except OSError:
            continue
        finally:
            sock.close()
    # Nothing free in range — return the base and let uvicorn fail
    # loudly, which is far better than guessing a busy port silently.
    return _PORT_BASE


def _write_port_file(port: int) -> None:
    """Publish the chosen port so the shell + orb can find the backend."""
    from pathlib import Path

    d = Path.home() / ".yumii"
    d.mkdir(parents=True, exist_ok=True)
    try:
        (d / "backend.port").write_text(str(port), encoding="utf-8")
    except OSError:
        pass  # non-fatal; the orb still discovers the port by probing


def _run_server() -> None:
    """Boot the FastAPI backend on a free loopback port (blocking)."""
    # onnxruntime/numpy can trip over duplicate OpenMP runtimes on
    # Windows; the desktop shell sets this too, but direct runs need it.
    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
    configure_logging()

    import uvicorn

    from yumii.api.server import app as fastapi_app

    port = _pick_free_port()
    _write_port_file(port)
    uvicorn.run(fastapi_app, host="127.0.0.1", port=port, log_config=None)


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
