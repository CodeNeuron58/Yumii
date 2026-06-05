# Changelog

All notable changes to Yumii will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.2.0] — 2026-06-05

Memory & Sessions release.

### Added
- **Persistent SQLite memory.** Two local databases at `~/.yumii/memory/`:
  `yumii.db` (session metadata + user facts) and `checkpoints.db`
  (LangGraph `AsyncSqliteSaver` conversation history). Survives server
  restarts.
- **Session management.** Each browser tab gets its own session ID.
  No more shared `yumii_session_1`. Sessions can be created, resumed,
  renamed, listed, and deleted.
- **Automatic fact extraction.** After every conversation turn, a cheap
  LLM pass extracts user facts ("user is vegetarian", "user likes jazz")
  and deduplicates them against existing memory. Facts are injected into
  the system prompt on every new / resumed session.
- **CLI session & memory commands:**
  - `/chat` — TUI session picker (resume, new, delete)
  - `/resume` — resume most recent session
  - `/sessions` — list all saved sessions
  - `/memory` — TUI fact browser / editor / deleter
  - `/forget` — wipe all long-term memory (facts, not sessions)
  - `/name <name>` — rename the active session
- **REST API endpoints** (`server.py`):
  - `GET/POST /api/sessions`, `POST /api/sessions/{id}/resume`,
    `DELETE /api/sessions/{id}`
  - `GET /api/facts`, `PUT /api/facts/{id}`, `DELETE /api/facts/{id}`
  - `GET /api/config` — runtime config + avatar URL
- **4 new test files** (`test_fact_extractor.py`, `test_memory_db.py`,
  `test_memory_manager.py`, `test_session_manager.py`).
- **New dependencies:** `aiosqlite`, `langgraph-checkpoint-sqlite`.

### Changed
- `graph.py` now uses `AsyncSqliteSaver` instead of `InMemorySaver`.
- `llm.py` agent cache key includes a hash of injected user facts, so
  personality updates correctly when memory changes.
- `engine.py` initializes lazily (async `initialize()`) because
  `AsyncSqliteSaver` needs an async context.

### Removed
- Dead frontend-only WebSocket broadcasts (`session_switched`,
  `session_renamed`, `session_taken_over`, `session_ready`,
  `memory_cleared`). The frontend never displayed these; they were
  scaffolding for a UI overlay that was reverted.

### Security
- Facts database is local SQLite only — no cloud storage.

## [0.1.0] — 2026-06-03

First public release. **Alpha — no API stability promise.** Everything
that works today may need to change in v1.0.0 once the Triage / Planner
/ Synthesizer agent loop lands. Don't build third-party plugins
against the current engine yet.

### Added
- Real-time voice conversation loop: Silero VAD → STT → LangGraph agent → TTS.
- Live2D avatar driven by LLM structured output (`YumiiResponse` with
  `response_text`, `expression`, `motion`).
- Six built-in personalities: `caring`, `tsundere`, `genki`, `kuudere`,
  `yandere`, `dandere`. Personality prompts are plain text files in
  `src/yumii/assets/prompts/`.
- Hot-swappable personality mid-conversation ("switch to tsundere").
- Three LLM providers: Groq (default, Llama-3.3-70b), OpenAI (gpt-4o),
  Anthropic (claude-3-5-sonnet). Swappable via the Attunement wizard.
- Two STT backends: `faster-whisper` (local CPU, default) and
  Groq Whisper (cloud, ~5–10× faster).
- Two TTS backends: ElevenLabs (default) and CAMB.ai (streaming).
- Barge-in / speech interruption (Gemini Live–style).
- OS-keychain credential storage (Windows Credential Manager, macOS
  Keychain, libsecret on Linux). No plaintext keys on disk.
- Auto-migration of any stale plaintext credentials from `config.json`
  into the OS keychain on first run.
- Polished Typer + Rich + prompt_toolkit CLI with a pixel-art banner,
  gradient vision reader, and a guided first-run Attunement wizard.
- One-line installers for Windows (`install.ps1`) and macOS / Linux
  (`install.sh`) that pin `torch` to the CPU-only wheel index.
- 24 unit tests covering the audio pipeline, credential store, global
  config, personality manager, and conversation state contract.

### Changed
- `uv` is the only supported package manager. `pip` will try to
  download the full 2 GB CUDA build of torch and fail. Both installers
  and the README warn about this.
- The Live2D model previously bundled for the zero-config demo has
  been **removed**. The bundled model was a third-party Live2D
  adaptation of a copyrighted character whose redistribution terms
  explicitly forbid secondary distribution. See `README.md` §3 and
  `docs/content/customization/adding-avatars.mdx` for the replacement
  flow. Voice + LLM work without an avatar.

### Security
- `uvicorn` is bound to `127.0.0.1` only. The default `main.py`
  shipped with `0.0.0.0` (exposes the dev server to the LAN), which
  was tightened before this release.
- All print-based logging replaced with `structlog`. No more stdout
  spam from the engine or from third-party libraries (uvicorn, httpx,
  LangChain).

### Known limitations (post-0.1.0)
- **No persistent memory across restarts.** Conversation history
  lives in LangGraph's `InMemorySaver` and is lost when the server
  exits. Planned for v1.1.
- **No planning / tool-execution agent loop.** A single LLM call
  produces one response. Multi-step tasks (e.g. "order food", "book
  a ride") are not supported. Planned for v2.0.
- **No MCP server.** Yumii does not yet expose its tool registry over
  the Model Context Protocol. Planned for v2.0.
- **No multimodal vision.** Yumii cannot see your screen or webcam.
  Planned for a post-v2.0 milestone.
- **Single shared conversation.** All WebSocket clients share one
  `thread_id` (`yumii_session_1`). Multi-user support is not in scope
  for the v0.1.x line.

## [0.x] — pre-release history

Prior to v0.1.0, Yumii was developed in a non-public form. Earlier
versions existed only as personal builds and were not tagged.
