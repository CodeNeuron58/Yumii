# How to Contribute to Yumi

Thank you for your interest in contributing! Yumi is designed to be open and modular.

## Prerequisites

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) — the project's package manager. Install it with:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # or on Windows (PowerShell):
  powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```

## Getting Started

1. Fork the repository on GitHub and clone your fork:
   ```bash
   git clone https://github.com/CodeNeuron58/Yumi.git
   cd Yumi
   ```

2. Install all dependencies (including dev tools):
   ```bash
   uv sync --extra dev
   ```
   > **Note:** Do NOT use `pip install`. The project pins `torch` to a
   > CPU-only wheel index via `[tool.uv.sources]` in `pyproject.toml`.
   > Regular pip will download the full CUDA build (~2 GB) or fail.

3. Run Yumi to set up your API keys. Either activate the venv first:
   ```bash
   # Windows
   .venv\Scripts\activate
   yumi

   # macOS / Linux
   source .venv/bin/activate
   yumi
   ```
   Or skip activation:
   ```bash
   uv run yumi
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
src/yumi/
  agent/          # LangGraph state machine + LLM agent
  api/            # FastAPI server + WebSocket broadcast
  audio/          # STT pipeline (Silero VAD + Whisper/Groq)
  core/           # Config, settings, OS keychain integration
  tts/            # ElevenLabs + CAMB.ai TTS speakers
  tools/          # LangChain tools (time, etc.)
  assets/
    prompts/      # Personality prompt files (.txt)
    webui/        # Frontend HTML (Live2D + PixiJS)
  cli.py          # Typer CLI entry point
```

> Avatar files go in `~/.yumi/avatar/` (user-provided, not bundled in the package).

## Pull Requests

- Provide a clear, descriptive title.
- Explain what changed and why.
- Ensure all CI checks pass.

We welcome contributions of all kinds: new personalities, prompt improvements,
UI enhancements, new tools, additional STT/TTS backends, and core pipeline features!
