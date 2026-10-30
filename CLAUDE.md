# Yumii — Project Context for AI Coding Tools

## What is Yumii?
An open-source, voice-first AI companion for the desktop: real-time voice
conversation (STT → LLM → TTS), tools, persistent memory, and 6 switchable
personalities. Memory lives locally in SQLite; API keys live in
`~/.yumii/auth.json` (owner-only file, the Claude Code / opencode model).

**The product is a native desktop app** (Tauri) with a notch-style **island**
UI at the top of the screen. The Python "brain" (engine, agent, audio, memory) runs as a backend the
desktop shell launches. The animated **Live2D companion/avatar** is a
long-term goal with no timeline; a pixel-art **desktop pet** skin is planned
(`checklists/checklist-ui-bar-and-pet.md`). **Proactiveness** (she speaks
first) is researched and designed but NOT built — see
`checklists/checklist-proactiveness.md`; don't bolt on a half version.
**Screen awareness** is next after that.

**Default mind (fresh installs):** NVIDIA Nemotron 3 Super on **Nebius Token
Factory** (OpenAI-compatible API, `NEBIUS_API_KEY`); background memory work
runs on Nemotron 3 Nano.

**GitHub:** https://github.com/CodeNeuron58/Yumii — `master` = latest release,
`develop` = next release (work lands here first; CI runs on both).

---

## Tech Stack
- **Language:** Python 3.12+ (backend) · Rust (desktop shell)
- **Package manager:** `uv` (NOT pip — `uv.lock` is the source of truth; CI
  runs `uv sync --locked`)
- **Backend:** FastAPI + Uvicorn + WebSocket (127.0.0.1 only; port 8000–8011)
- **Frontend:** vanilla HTML/CSS + native ES modules, **no build step**
  (`src/yumii/assets/webui/`): `index.html` (the island) and `dashboard.html`
  are thin shells over `ui/` — `tokens.css` (design tokens, bundled Geist
  fonts), `backend.js` (port discovery, REST, shell IPC), `voice.js`
  (WebSocket, mic, playback), `island.js` (one state object → `view()` →
  render), `dashboard.js`. Every dynamic string goes through `esc()` or a
  `[data-text]` slot. Design-review any island state with
  `index.html?preview=<view>`. The old Live2D UI is archived (not served) as
  `_companion_live2d.reference.html`.
- **Desktop shell:** **Tauri v2** (`desktop/src-tauri/`) — frameless,
  transparent, always-on-top island the page sizes via `set_island_size`;
  tray + global hotkey; launches the backend
  (`python -m yumii server`, or the installed `yumii server`) as a managed child.
- **AI framework:** LangChain + LangGraph (`langgraph>=1.2`)
- **LLM providers:** 12, data-driven via `core/model_catalog.py`
  (`PROVIDER_WIRING` + a models.dev snapshot): **Nebius Token Factory
  (default)**, Groq, Google, OpenRouter, DeepSeek, xAI, Together, Mistral,
  OpenCode, Ollama (local or cloud), OpenAI, Anthropic. Background jobs use
  the provider's cheap tier (`cheap_model_for`).
- **STT:** local faster-whisper (default) · Groq Whisper · Vosk · NVIDIA
  Nemotron Speech + Moonshine via sherpa-onnx (experimental)
- **VAD / turn-taking:** Silero VAD (bundled ONNX, no torch) + Smart Turn v3
- **TTS:** Kokoro-82M (local ONNX, default) · ElevenLabs · CAMB.ai
- **Web search:** Tavily (with `TAVILY_API_KEY`) → DuckDuckGo fallback
- **CLI:** none (retired; preserved on the `cli-launch` branch).
  `yumii server` is a bare launcher the desktop shell invokes.

---

## Project Structure
```
src/yumii/
  agent/          # LangGraph agent → tools loop (graph.py), LLM factory + prompt
                  # assembly + voice anchor (llm.py), personality switch (nodes.py),
                  # heuristic emotion/motion + speech cleaner (synthesizer.py)
  api/            # FastAPI server, WebSocket, /health, /api/status, REST (sessions,
                  # facts, settings, model picker, Composio)
  audio/          # Capture pipeline (stt.py: Silero VAD + Smart Turn), STT providers
    providers/    # one self-registering module per STT provider
  core/           # config, auth.json credential store, engine (asyncio tasks),
                  # memory (memory_db, memory_manager, transcript FTS, summarizer),
                  # model_catalog, providers.py (STT/TTS registry), first-run models.py
  tts/            # Kokoro / ElevenLabs / CAMB speakers + sentence streaming
    providers/    # one self-registering module per TTS provider
  tools/          # tool registry + ToolPolicy/HITL, time, web search (Tavily/ddgs),
                  # manage_memory, search_past_conversations, Composio loader
  assets/
    prompts/      # _core.txt + 6 personality .txt files
    webui/        # index.html (island) + dashboard.html + ui/ modules, styles, fonts
    model_catalog.json, models/silero_vad.onnx
  cli.py          # bare launcher: `yumii server`

desktop/src-tauri/  # Tauri v2 shell: main.rs (window, tray, hotkey, backend child)
checklists/         # owner's planning notes (gitignored)
```

---

## Critical Rules
1. **NEVER use `pip install`** — always `uv sync --extra dev`. Never hand-edit
   `uv.lock`. `sherpa-onnx` and `sherpa-onnx-core` are pinned to the SAME version
   — bump them together (without core, Windows segfaults on a stale system
   onnxruntime.dll).
2. **API keys live in `~/.yumii/auth.json`** (owner-only, atomic writes) —
   never in .env files and never in config.json. Use `credential_store.py`; new
   keys must be added to its `CREDENTIAL_KEYS` allowlist. (A `.env` at the repo
   root is gitignored and NOT read by the app.)
3. **Non-sensitive config** (personality, provider choice) lives in `~/.yumii/config.json`.
4. **Avatar files** (user-provided Live2D models, for the future companion mode) live in `~/.yumii/avatar/`.
5. **Asset files** (prompts, webui) live in `src/yumii/assets/` — inside the package, so they're bundled in the wheel.
6. **Desktop build output** (`desktop/src-tauri/target/`) is gitignored — never commit it.
7. **Everything she says is spoken aloud.** Prompt changes must be checked against
   real model output (short replies, few questions, no emojis/markdown — the
   speech cleaner in `synthesizer.py` enforces the last part in code).

---

## Entry Points
- **Desktop app (the ONLY product surface):** `cd desktop && npx @tauri-apps/cli dev`
- `yumii server` / `python -m yumii server` → FastAPI on `127.0.0.1:8000` (walks
  up to 8011 if taken; writes `~/.yumii/backend.port`).
- WebSocket: `ws://127.0.0.1:<port>/ws` (binary PCM16 audio in, JSON events out;
  first frame must be `session_select`)
- Health probe: `GET /health`; first-run state: `GET /api/status`
- The backend serves ONLY `/dashboard.html` and its `/ui` assets; the island
  is rendered by the Tauri shell from its own copy of the same folder.

---

## Key Design Decisions
- **asyncio Queues** between three concurrent tasks: audio_listener → reasoning_engine → tts_speaker
- **Generation counter + interrupt_event** for barge-in; speech from an older
  generation is dropped
- **Token → sentence → TTS streaming**; Kokoro prefetch worker; synthesis cache
- **AsyncSqliteSaver** checkpoints + **AsyncSqliteStore** facts + a `messages`
  FTS5 transcript index — all under `~/.yumii/memory/`, surviving restarts
- **Per-session `thread_id`**; the last session resumes after a restart
- **Native tool-calling** via `bind_tools` (custom `StateGraph` + `ToolNode`);
  emotion/motion come from a **heuristic regex synthesizer**, not LLM output
- **Prompt assembly is cache-ordered:** static core + persona → "mind" line
  (which model, and what leaves the machine) → date → session context →
  facts → history → **voice anchor** (a short reminder restated after the
  history every call, carrying the clock time; not sent to Anthropic)
- **Nemotron on Nebius runs with reasoning off** (`extra_body`
  `chat_template_kwargs.enable_thinking=false`) — measured latency, and some
  templates otherwise leak thinking into spoken content; a one-token warm-up
  absorbs serverless cold starts
- **HITL confirmation gate** for tool calls (`settings.hitl_mode`: never / external / always)
- **Memory:** the agent writes facts with `manage_memory`; a background review
  every 5 turns and rolling session summaries run on the cheap tier
- **Provider registry** (`core/providers.py`): STT/TTS providers register
  themselves; factories, first-run downloads and dashboard choices derive from it
- **File-based credentials** (`~/.yumii/auth.json`, 0600, atomic tmp+rename writes)

---

## Commands
```bash
uv sync --extra dev     # Install Python dependencies (dev tools included)
uv run yumii server     # Run the backend headless (the desktop app calls this)
uv run ruff check .     # Lint
uv run pytest tests/    # Tests
uv build                # Build the Python wheel

cd desktop && npx @tauri-apps/cli dev   # Run the desktop app — the only way to run Yumii
```
