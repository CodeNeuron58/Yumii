# How to Contribute to Yumii

Thank you for your interest in contributing! Yumii is designed to be open and modular.

## Prerequisites

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) — the project's package manager:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # or on Windows (PowerShell):
  powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```
- For the desktop app: [Rust](https://rustup.rs), Node.js, and on Windows the
  MSVC C++ Build Tools.

## Getting Started

1. Fork the repository on GitHub and clone your fork:
   ```bash
   git clone https://github.com/CodeNeuron58/Yumii.git
   cd Yumii
   ```

2. Install all dependencies (including dev tools):
   ```bash
   uv sync --extra dev
   ```
   > **Note:** Do NOT use `pip install`. `uv.lock` pins every dependency (CI
   > installs with `uv sync --locked`), including native packages like
   > `sherpa-onnx` that must move together with their runtime.

3. Run the desktop app:
   ```bash
   cd desktop
   npx @tauri-apps/cli dev
   ```
   On first launch Yumii downloads her voice model and asks for one API key
   (by default a [Nebius Token Factory](https://tokenfactory.nebius.com/project/api-keys)
   key for NVIDIA Nemotron). Keys are stored in `~/.yumii/auth.json` (an
   owner-only file) — never in a `.env` file, which has no effect. Everything
   else is in the dashboard (tray icon → Dashboard).

4. Branch from `develop` (the next release; `master` is the latest release):
   ```bash
   git checkout develop
   git checkout -b feature/my-new-feature
   ```

## Development Workflow

- **Lint:** `uv run ruff check .`
- **Tests:** `uv run pytest tests/`

Run both before opening a PR, and add tests for new functionality. Pull
requests target `develop`.

## The easiest contributions

- **A personality** is one text file in
  [`src/yumii/assets/prompts/`](src/yumii/assets/prompts/). Copy one, rewrite
  the character, keep the example lines short (they're spoken aloud, and the
  model copies them), and open a PR.
- **A speech-to-text or voice provider** is one self-registering module:
  `src/yumii/audio/providers/<name>.py` or `src/yumii/tts/providers/<name>.py`.
  Call `register(...)` at import with an id, a label and any credential keys,
  define `build(spec)` (plus `present(spec)` / `provision(spec, report)` if it
  downloads a local model), and add one import line to the package's
  `__init__.py`. The dashboard, first-run downloads and factories pick it up
  from the registry (`src/yumii/core/providers.py`); `tests/test_provider_registry.py`
  checks you didn't miss anything. New credential keys go in
  `CREDENTIAL_KEYS` in `core/credential_store.py`.
- **An LLM provider** with an OpenAI-compatible API is one entry in
  `PROVIDER_WIRING` in `src/yumii/core/model_catalog.py`.

## Project Structure

```
src/yumii/
  agent/          # LangGraph agent → tools loop, LLM factory + prompt assembly, synthesizer
  api/            # FastAPI server + WebSocket + REST
  audio/          # capture pipeline (Silero VAD + Smart Turn) and STT providers/
  core/           # config, credentials, engine, memory, model catalog, provider registry
  tts/            # speakers + sentence streaming, and TTS providers/
  tools/          # tool registry + permission policy; web search, memory, past-conversation search
  assets/
    prompts/      # _core.txt + personality files
    webui/        # top bar (index.html) + dashboard.html; archived Live2D UI
  cli.py          # `yumii server` launcher

desktop/          # Tauri v2 desktop app (Rust) — renders the bar, launches the backend
```

> User-provided Live2D models (for the future companion mode) go in
> `~/.yumii/avatar/` — not bundled in the package.

## Pull Requests

- Provide a clear, descriptive title.
- Explain what changed and why.
- Ensure all CI checks pass.

We welcome contributions of all kinds: new personalities, prompt improvements,
UI enhancements, new tools, additional STT/TTS backends, and core pipeline features!
