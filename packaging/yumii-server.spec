# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Yumii backend sidecar.

Freezes packaging/yumii_server.py into dist/yumii-server/ (onedir). The
hard parts of this app are DATA and NATIVE files PyInstaller's static
analysis can't infer:

  * Yumii's own package data — prompts, webui HTML, the Silero ONNX model.
  * ML deps that ship binaries + data (kokoro-onnx + espeak, faster-whisper,
    vosk).
  * langchain / composio / provider SDKs read their own package metadata
    at import time, so that metadata must be copied in or import crashes.

Build:  uv run pyinstaller --noconfirm packaging/yumii-server.spec
Run:    dist/yumii-server/yumii-server.exe   (then curl /health)
"""

from PyInstaller.utils.hooks import (
    collect_all,
    collect_data_files,
    collect_submodules,
    copy_metadata,
)

datas = []
binaries = []
hiddenimports = []

# --- Yumii's own package data (the first crash: silero_vad.onnx) ---
datas += collect_data_files("yumii")  # prompts/*.txt, webui/*.html, models/*.onnx

# --- Packages that ship data files PyInstaller's analysis can't infer ---
# (native binaries, grammars, JSON schemas, CA bundles, token tables).
for _pkg in (
    "kokoro_onnx",              # onnx config / vocab json
    "espeakng_loader",          # espeak-ng native lib + data (phonemizer backend)
    "phonemizer",               # phonemizer-fork data
    "language_tags",            # kokoro dep, json data tables
    "faster_whisper",           # bundled assets
    "rfc3987_syntax",           # .lark grammar (via jsonschema URI format)
    "jsonschema",               # schema validation (composio/langchain tools)
    "jsonschema_specifications",  # bundled JSON schema drafts
    "referencing",              # jsonschema dep, ships data
    "certifi",                  # CA bundle — HTTPS to Groq/Composio/Ollama
    "tiktoken",                 # token-encoding data
):
    try:
        _d, _b, _h = collect_all(_pkg)
        datas += _d
        binaries += _b
        hiddenimports += _h
    except Exception:
        pass  # not every package is installed on every machine

# --- Packages that read importlib.metadata.version() at import time ---
for _pkg in (
    "langchain", "langchain_core", "langchain_community",
    "langchain_groq", "langchain_openai", "langchain_anthropic",
    "langchain_ollama", "langgraph",
    "groq", "openai", "anthropic", "ollama",
    "composio", "composio_langchain",
    "tqdm", "regex", "numpy",
):
    try:
        datas += copy_metadata(_pkg)
    except Exception:
        pass

# --- Dynamically imported submodules PyInstaller may miss ---
# uvicorn picks its event loop / http protocol impls at runtime.
hiddenimports += collect_submodules("uvicorn")


a = Analysis(
    ["yumii_server.py"],
    pathex=["../src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter", "matplotlib", "IPython", "jupyter", "jupyterlab",
        "notebook", "pytest", "_pytest", "pytest_asyncio",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="yumii-server",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,  # Phase 1: keep the console so crashes are visible
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="yumii-server",
)
