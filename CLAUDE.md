# Yumii — Project Context for AI Coding Tools

## What is Yumii?
An open-source, locally-runnable AI companion with real-time voice
conversation (STT → LLM → TTS) and 6 switchable personalities. Memory lives
locally in SQLite; API keys live in `~/.yumii/auth.json` (owner-only file, the
Claude Code / opencode model). Runs on CPU (cloud STT/LLM by default, or fully
local models).

**Current direction:** Yumii is pivoting from a browser-served Live2D page to a
**native desktop app** (Tauri) with a small floating **orb** UI. The animated
**Live2D companion/avatar is a planned "coming soon" mode** — the shipped
frontend today is the orb. The Python "brain" (engine, agent, audio, memory) is
unchanged by the pivot; the desktop app wraps it.

**GitHub:** https://github.com/CodeNeuron58/Yumii

---

## Tech Stack
- **Language:** Python 3.12+ (backend) · Rust (desktop shell)
- **Package manager:** `uv` (NOT pip — torch is pinned to CPU-only wheels)
- **Backend:** FastAPI + Uvicorn + WebSocket
- **Frontend:** single-file vanilla HTML/CSS/JS **orb** UI
  (`src/yumii/assets/webui/index.html`). The old Live2D + PixiJS UI is archived
  (not served) as `src/yumii/assets/webui/_companion_live2d.reference.html` for
  the future companion mode.
- **Desktop shell:** **Tauri v2** (`desktop/src-tauri/`) — frameless,
  transparent, always-on-top orb window; system tray + global hotkey; launches
  the Python backend (`python -m yumii server`) as a managed subprocess.
- **AI framework:** LangChain + LangGraph (`langgraph>=1.2`)
- **LLM providers:** Groq (default; model configurable via `GROQ_MODEL`, default qwen3.6-27b), OpenAI (gpt-4o), Anthropic (claude-3-5-sonnet)
- **STT:** faster-whisper (local, CPU, int8) OR Groq Whisper (cloud) OR Vosk (local, streaming partials)
- **VAD:** Silero VAD (snakers4/silero-vad via torch.hub) — always local
- **TTS:** Kokoro-82M (local ONNX, recommended default) OR ElevenLabs OR CAMB.ai (all streaming)
- **CLI:** none (retired with the desktop pivot; preserved on the `cli-launch`
  branch). `yumii server` is a bare launcher the desktop shell invokes.

---

## Project Structure
```
src/yumii/
  agent/          # LangGraph state machine (graph.py): agent → tools → agent loop,
                  # LLM factory (llm.py), personality-switch detector (nodes.py),
                  # heuristic emotion/motion synthesizer (synthesizer.py),
                  # fact_extractor, personality_manager
  api/            # FastAPI server, WebSocket endpoint, /health, REST (sessions, facts, config)
  audio/          # STT pipeline: Silero VAD + Whisper/Groq
  core/           # Config (Pydantic Settings), auth.json credential store, engine orchestrator,
                  # memory_db (SQLite), memory_manager, session_manager
  tts/            # Kokoro (local) + ElevenLabs + CAMB.ai speakers
  tools/          # LangChain tools + registry/policy: get_current_time, web_search,
                  # tool registry, ToolPolicy, MCP config loader
  assets/
    prompts/      # 6 personality .txt files (caring, tsundere, genki, kuudere, yandere, dandere)
    webui/        # index.html (orb) + _companion_live2d.reference.html (archived)
  cli.py          # bare launcher: `yumii server` (no interactive CLI)

desktop/
  src-tauri/      # Tauri v2 Rust app: main.rs (window, tray, hotkey, Python sidecar),
                  # tauri.conf.json, Cargo.toml, capabilities/, icons/
```

---

## Critical Rules
1. **NEVER use `pip install`** — always `uv sync`. torch is pinned to CPU-only index.
2. **API keys live in `~/.yumii/auth.json`** (owner-only permissions, atomic writes) —
   never in .env files and never in config.json. Use `credential_store.py`.
   (A `.env` at the repo root is gitignored and NOT read by the app. The old
   OS-keychain storage is gone; a one-time migration copies legacy entries.)
3. **Non-sensitive config** (personality, provider choice) lives in `~/.yumii/config.json`.
4. **Avatar files** (user-provided Live2D models, for the future companion mode) live in `~/.yumii/avatar/`.
5. **Asset files** (prompts, webui) live in `src/yumii/assets/` — inside the package, so they're bundled in the wheel.
6. **Desktop build output** (`desktop/src-tauri/target/`) is gitignored — never commit it.

---

## Entry Points
- **Desktop app (the ONLY product surface):** `cd desktop && npx @tauri-apps/cli dev` (or `cargo tauri dev`)
- `yumii server` / `python -m yumii server` → starts FastAPI on `127.0.0.1:8000` (headless; this is what the desktop shell launches). Bare `yumii` just prints usage.
- WebSocket: `ws://127.0.0.1:8000/ws` (binary audio in, JSON events out)
- Health probe: `GET /health` (used by the desktop shell before connecting the WS)
- The backend serves ONLY `/dashboard.html` (the shell's dashboard window) — there is no browser orb; the orb page is rendered by the Tauri shell from its own assets. Browser mode is retired (preserved on `cli-launch`).

---

## Key Design Decisions
- **asyncio Queues** between three concurrent tasks: audio_listener → reasoning_engine → tts_speaker
- **interrupt_event: asyncio.Event** enables barge-in (Gemini Live style)
- **AsyncSqliteSaver** for LangGraph checkpoints + **AsyncSqliteStore** for user facts — both at `~/.yumii/memory/`, survive restarts
- **SessionManager** sits on top of a low-level `memory_db.py` SQLite layer (sessions, session_summaries); **MemoryManager** uses LangGraph's own `AsyncSqliteStore` at a separate `store.db` file
- **Per-session `thread_id`** for LangGraph checkpoints; no single shared session
- **Native tool-calling IS enabled** — the agent binds tools via `bind_tools` (custom `StateGraph` + `ToolNode`). Emotion/motion are NOT structured LLM output; a **heuristic regex synthesizer** (`agent/synthesizer.py`) derives `expression`/`motion` from the plain-text reply after the final turn. Current time is injected as a per-turn `SystemMessage` in addition to the `get_current_time` tool.
- **HITL confirmation gate** for tool calls (`settings.hitl_mode`: never / external / always)
- **Fire-and-forget fact extraction** after every turn using a cheap LLM pass (Groq `llama-3.1-8b-instant` by default); deduplicated against existing memory
- **beam_size=1** in Whisper — greedy decoding, fastest CPU inference, low latency trade-off
- **File-based credentials** (`~/.yumii/auth.json`, 0600, atomic tmp+rename writes) —
  the Claude Code / opencode model; replaced the OS keychain (keyring), which was
  a packaging/portability tax and invisible to users

---

## Commands
```bash
uv sync                 # Install Python dependencies
uv run yumii server     # Run the backend headless (the desktop app calls this)
uv run ruff check .     # Lint
uv run pytest tests/    # Tests
uv build                # Build the Python wheel

cd desktop && npx @tauri-apps/cli dev   # Run the desktop app — the only way to run Yumii
```
