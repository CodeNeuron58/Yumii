"""Atomic, timeout-bounded file downloads for first-run model provisioning.

Every model fetch (whisper, vosk, kokoro, smart turn) goes through here so
a stalled connection can never hang first-run boot: raw urlretrieve has no
read timeout, but this helper bounds every socket read and raises on
failure instead of blocking forever. Writes are atomic (.part + os.replace),
so ``dest`` is never left half-written for a later boot to trust.
"""

import os
import time
import urllib.request
from pathlib import Path
from typing import Callable

from yumii.core.logging import get_logger

log = get_logger(__name__)

# Bounds every socket read; a big model just needs many successful reads.
_READ_TIMEOUT_SEC = 30.0


def download_file(
    url: str,
    dest: Path,
    progress: Callable[[float], None] | None = None,
) -> None:
    """Download *url* to *dest* atomically (.part + os.replace).

    ``progress`` receives the overall fraction (0..1) derived from
    Content-Length when the server sends it. Raises on any failure — the
    .part file is removed and ``dest`` is untouched.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "yumii"})
    log.info("model_download_started", url=url, target=str(dest))

    total: int | None = None
    done = 0
    try:
        with urllib.request.urlopen(request, timeout=_READ_TIMEOUT_SEC) as resp:
            length = resp.headers.get("Content-Length")
            total = int(length) if length else None
            with open(part, "wb") as fh:
                while True:
                    block = resp.read(256 * 1024)
                    if not block:
                        break
                    fh.write(block)
                    done += len(block)
                    if progress and total:
                        progress(min(1.0, done / total))
    except Exception:
        part.unlink(missing_ok=True)
        raise

    if total is not None and done != total:
        part.unlink(missing_ok=True)
        raise IOError(f"Truncated download ({done}/{total} bytes): {url}")

    os.replace(part, dest)
    log.info("model_download_done", file=dest.name, bytes=done)


class _ProgressClock:
    """Throttles progress callbacks so the first-run bar updates ~5x/sec."""

    def __init__(self, sink: Callable[[float], None], interval: float = 0.2):
        self._sink = sink
        self._interval = interval
        self._last = 0.0

    def __call__(self, fraction: float) -> None:
        now = time.monotonic()
        if fraction >= 1.0 or now - self._last >= self._interval:
            self._last = now
            self._sink(fraction)
