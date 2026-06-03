# Yumii — Project Context for AI Coding Tools

## What is Yumii?
An open-source, locally-runnable AI companion with a Live2D anime avatar,
real-time voice conversation (STT → LLM → TTS), and 6 switchable personalities.
Runs entirely on CPU. No GPU required.

**GitHub:** https://github.com/CodeNeuron58/Yumii

---

## Tech Stack
- **Language:** Python 3.12+
- **Package manager:** `uv` (NOT pip — torch is pinned to CPU-only wheels)
- **Backend:** FastAPI + Uvicorn + WebSocket
- **Frontend:** Vanilla HTML + PixiJS 6 + Live2D Cubism SDK (single file: `src/yumii/assets/webui/index.html`)
- **AI framework:** LangChain + LangGraph (`langgraph>=1.0`)
- **LLM providers:** Groq (default, llama-3.3-70b), OpenAI (gpt-4o), Anthropic (claude-3-5-sonnet)
- **STT:** faster-whisper (local, CPU, int8) OR Groq Whisper (cloud)
- **VAD:** Silero VAD (snakers4/silero-vad via torch.hub)
- **TTS:** ElevenLabs (default) OR CAMB.ai (streaming)
- **CLI:** Typer + Rich + questionary

---

## Project Structure
```
src/yumii/
  agent/          # LangGraph state machine (graph.py), LLM factory (llm.py),
                  # reasoning node (nodes.py), personality manager
  api/            # FastAPI server + WebSocket endpoint
  audio/          # STT pipeline: Silero VAD + Whisper/Groq
  core/           # Config (Pydantic Settings), OS keychain, engine orchestrator
  tts/            # ElevenLabs + CAMB.ai speakers
  tools/          # LangChain tools (currently: get_current_time)
  assets/
    prompts/      # 6 personality .txt files (caring, tsundere, genki, kuudere, yandere, dandere)
    webui/        # Single-file frontend: index.html
cli.py            # Typer CLI entry point (yumii command)
```

---

## Critical Rules
1. **NEVER use `pip install`** — always `uv sync`. torch is pinned to CPU-only index.
2. **API keys live in the OS keychain** — never in .env files. Use `credential_store.py`.
3. **Non-sensitive config** (personality, provider choice) lives in `~/.yumii/config.json`.
4. **Avatar files** (user-provided Live2D models) live in `~/.yumii/avatar/`.
5. **Asset files** (prompts, webui) live in `src/yumii/assets/` — inside the package, so they're bundled in the wheel.

---

## Entry Points
- `yumii` CLI command → `src/yumii/cli.py:app`
- `yumii wake-up` → starts FastAPI on `localhost:8000`, opens browser
- WebSocket: `ws://localhost:8000/ws` (binary audio in, JSON events out)
- Frontend served at: `http://localhost:8000/`

---

## Key Design Decisions
- **asyncio Queues** between three concurrent tasks: audio_listener → reasoning_engine → tts_speaker
- **interrupt_event: asyncio.Event** enables barge-in (Gemini Live style)
- **InMemorySaver** for LangGraph memory — intentionally for prototype (production would use SQLite/Redis)
- **beam_size=1** in Whisper — greedy decoding, fastest CPU inference, low latency trade-off
- **OS keychain** via `keyring` library — security-first, no plaintext secrets

---

## Commands
```bash
uv sync              # Install dependencies
uv run yumii          # Launch dashboard / run app
uv run ruff check .  # Lint
uv run pytest tests/ # Tests
uv build             # Build wheel
```
