"""Frozen entry point for the Yumii backend (what PyInstaller builds).

Boots the FastAPI app directly with uvicorn — no Typer CLI, no
interactive shell. The Tauri shell will launch this instead of
`python -m yumii server`.
"""
import multiprocessing
import os


def main() -> None:
    # onnxruntime/numpy can trip over duplicate OpenMP runtimes; the app
    # sets this everywhere, so the frozen entry point must too.
    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

    import uvicorn
    from yumii.api.server import app

    uvicorn.run(app, host="127.0.0.1", port=8000, log_config=None)


if __name__ == "__main__":
    # Frozen apps that spawn subprocesses must call this FIRST, or each
    # child re-runs the whole program. Some ML libs use multiprocessing.
    multiprocessing.freeze_support()
    main()
