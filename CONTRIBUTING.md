# How to Contribute to Yumii

Thank you for your interest in contributing! Yumii is designed to be open and modular.

## Prerequisites

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) — the project's package manager. Install it with:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # or on Windows (PowerShell):
  powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```
- *(Optional — only for the desktop app)* [Rust](https://rustup.rs) + the MSVC
  C++ Build Tools on Windows. Then `cd desktop && cargo tauri dev`. The Python
  backend and browser UI need none of this.

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
   > **Note:** Do NOT use `pip install`. The project pins `torch` to a
   > CPU-only wheel index via `[tool.uv.sources]` in `pyproject.toml`.
   > Regular pip will download the full CUDA build (~2 GB) or fail.

3. Run Yumii to set up your API keys. Either activate the venv first:
   ```bash
   # Windows
   .venv\Scripts\activate
   yumii

   # macOS / Linux
   source .venv/bin/activate
   yumii
   ```
   Or skip activation:
   ```bash
   uv run yumii
   ```
   The first-run wizard stores your keys securely in your OS keychain.
   Do **not** create a `.env` file — it will have no effect.

4. Create a feature branch:
   ```bash
   git checkout -b feature/my-new-feature
   ```

## Development Workflow

- **Lint & format:** `uv run ruff check . && uv run ruff format .`
- **Type check:** `uv run mypy src/`
- **Tests:** `uv run pytest tests/`

Run all three before opening a PR. Make sure to add tests for any new functionality.

## Project Structure

```
src/yumii/
  agent/          # LangGraph state machine + tool-bound LLM agent + synthesizer
  api/            # FastAPI server + WebSocket + /health
  audio/          # STT pipeline (Silero VAD + Whisper/Groq)
  core/           # Config, settings, OS keychain integration
  tts/            # ElevenLabs + CAMB.ai TTS speakers
  tools/          # LangChain tools + registry/policy (time, web search)
  assets/
    prompts/      # Personality prompt files (.txt)
    webui/        # Orb UI (index.html); Live2D UI archived as _companion_live2d.reference.html
  cli.py          # Typer CLI entry point

desktop/          # Tauri v2 desktop app (Rust) — wraps the web UI, launches the Python backend
```

> User-provided Live2D models (for the coming companion mode) go in
> `~/.yumii/avatar/` — not bundled in the package.

## Pull Requests

- Provide a clear, descriptive title.
- Explain what changed and why.
- Ensure all CI checks pass.

We welcome contributions of all kinds: new personalities, prompt improvements,
UI enhancements, new tools, additional STT/TTS backends, and core pipeline features!
