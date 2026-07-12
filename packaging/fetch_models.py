"""Stage the Kokoro model files for the installer to bundle.

Populates ``packaging/build-models/kokoro/`` with the default (fp32)
model + voices so the desktop bundle can ship them — a fresh install
then needs no download. Prefers copying from the local
``~/.yumii/models`` cache (fast); otherwise downloads from the
kokoro-onnx release. Run this before ``tauri build``.
"""

import os
import shutil
import urllib.request
from pathlib import Path

_RELEASE = (
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
)
# fp32 model (the default; int8 is slower on x86) + the shared voice bank.
_FILES = ["kokoro-v1.0.onnx", "voices-v1.0.bin"]

DEST = Path(__file__).parent / "build-models" / "kokoro"
CACHE = Path.home() / ".yumii" / "models" / "kokoro"


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    for name in _FILES:
        target = DEST / name
        if target.exists():
            print(f"[models] have {name}")
            continue
        cached = CACHE / name
        if cached.exists():
            print(f"[models] copying {name} from local cache")
            shutil.copy2(cached, target)
        else:
            print(f"[models] downloading {name} ...")
            part = target.with_suffix(target.suffix + ".part")
            urllib.request.urlretrieve(f"{_RELEASE}/{name}", str(part))
            os.replace(part, target)
    print(f"[models] ready in {DEST}")


if __name__ == "__main__":
    main()
