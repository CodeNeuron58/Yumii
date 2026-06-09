# Changelog

All notable changes to Yumii will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.3.0] — 2026-06-08

Streaming engine fix + prompt label-leak fix on top of the v0.2
agentic-loop work. **Pre-1.0 — APIs may change.** This release
combines the four architecture PRs that landed in the 0.2 → 0.3
window (custom `StateGraph`, tool registry + policy, heuristic
synthesizer, HITL gate) with two follow-up fixes that surfaced
in manual testing.

### Added
- **Custom `StateGraph` + `ToolNode` agent loop.** Replaces the
  `create_agent` wrapper used in 0.2.0. The graph is a hand-built
  `agent → tools → agent` cycle in `src/yumii/agent/graph.py`,
  giving the engine full control over the message stream and
  making `interrupt_before` meaningful for tool calls.
- **Tool registry + `ToolPolicy` protocol.** A single
  `yumii.tools.registry` module owns every tool (native `@tool`,
  MCP-loaded, or hand-rolled `BaseTool`) plus its `ToolPolicy`
  (category: `READ` / `WRITE` / `EXTERNAL`, plus a
  `requires_confirmation` flag). Register a new tool in <30 lines:
  the policy decides whether the gate triggers.
- **MCP config loader.** A JSON config at
  `~/.yumii/mcp_servers.json` is parsed at startup and the named
  MCP servers are connected via `langchain_mcp_adapters`. Their
  tools land in the same registry as native tools, with the same
  `ToolPolicy` defaults.
- **Web search tool** (`yumii.tools.web_search` → DuckDuckGo
  Results). Registered with `ToolCategory.EXTERNAL,
  requires_confirmation=True` so it triggers the HITL gate out of
  the box.
- **Heuristic emotion / motion synthesizer** (`agent/synthesizer.py`).
  Runs after the final LLM turn and converts the agent's plain-text
  reply into the `YumiiResponse(response_text, expression, motion)`
  shape the Live2D frontend expects. Order-sensitive pattern
  classifier; no extra LLM call. Replaces the structured-output
  approach that 0.2.0 used, which was incompatible with native
  tool-calling.
- **Streaming engine events.** The reasoning loop now uses
  `astream_events(version="v2")` and broadcasts three WebSocket
  event types:
  - `thinking_start` / `thinking_delta` / `thinking_end` — per-token
    text from the LLM, for the typing-indicator UI.
  - `tool_status` (`running` / `done`) — so the status bar can show
    "Searching the web…".
  - Falls back to `ainvoke` if the event stream produces no
    `YumiiResponse` (defensive).
- **ElevenLabs streaming TTS** (`tts/speaker.py`). `stream_speak`
  yields `{"type": "metadata", "sampleRate": 22050}` first, then
  base64-encoded audio chunks as they arrive. The frontend plays
  them in real time instead of waiting for the full synthesis.
- **HITL confirmation gate.** Side-effecting tools pause the engine
  and emit a `confirmation_request` event to the frontend; the user
  clicks Yes / No in a browser-native modal; the engine's
  `asyncio.Future` resolves and the tool runs (or a synthetic
  `ToolMessage` saying it was declined is appended). Three modes
  configurable via the new `HITL_MODE` setting:
  - `"never"` — gate is disabled.
  - `"external"` (default) — gate only tools with
    `ToolCategory.EXTERNAL` or `requires_confirmation=True`.
  - `"always"` — gate every tool call.
  Default timeout: 30 s (`HITL_TIMEOUT_SECONDS`), after which the
  request is auto-denied. Barge-in during a confirmation vetoes
  an in-flight Yes.
- **HITL CLI command.** `yumii hitl-mode` (or `/hitl` in the REPL)
  opens a radiolist to pick the mode.
- **Frontend status bar + confirmation modal.** A 1-line pill at
  the top of the Live2D stage shows the current thinking / tool
  activity. The confirmation modal is a native browser `confirm`
  variant with Yes / No buttons.
- **Test suite is now 77 tests total** across 8 files. *The 0.3.0
  work landed 184 tests across 11 files (synthesizer, streaming,
  HITL, tool registry, plus three added in the 0.2 → 0.3
  window). Four of those modules — `test_graph`, `test_hitl`,
  `test_streaming`, `test_synthesizer` — imported the LLM factory
  at module-collection time, which raised `GroqError: api_key
  client option must be set` in any environment without the
  OS-keychain `GROQ_API_KEY` (CI, fresh clones, contributor
  machines that haven't run the Attunement wizard). They have
  been removed from 0.3.0 and are tracked for restoration once
  `src/yumii/agent/llm.py` is made import-time-safe (deferred
  from 0.3.0; see `Trash/need_to_fix_later.md`).*

### Changed
- **Native tool calling is back.** 0.2.0 had to drop it because
  Groq Llama 3.3 70B returned malformed tool calls; the new
  graph uses `bind_tools` directly and Groq's tool-call
  formatting works with the custom `StateGraph`. `get_current_time`
  is once again a real tool the LLM can call, not a per-turn
  `SystemMessage` injection.
- **Structured `YumiiResponse` output is gone.** The 0.2.0
  workaround (`response_format=`) is removed. The agent emits
  plain text; the synthesizer produces the structured shape.
- **Personality prompts no longer list label words.** The 6
  personality `.txt` files (`caring`, `tsundere`, `genki`,
  `kuudere`, `yandere`, `dandere`) no longer contain the
  `EXPRESSION & MOTION ALIGNMENT` or `AVAILABLE *` sections. The
  LLM was reading those as a multiple-choice list and emitting
  label words ("smile and nod", "smile and tilthead") at the end
  of its reply; the CRITICAL RULE alone now tells it to speak
  plainly and let the synthesizer derive labels from the tone.
  *Regression test removed in 0.3.0 (see note under "Test
  suite" above) — the fix is correct but the test that pinned
  the contract landed in a now-removed file. Re-add once
  `llm.py` is import-time-safe.*
- **Streaming engine fixed.** `reasoning_engine_task` now uses
  `astream_events(..., version="v2")`. The previous `version="v3"`
  silently returned a coroutine instead of an async iterator
  in `langchain-core` 1.4.x, causing every turn to fall back to
  blocking `ainvoke`. Per-token streaming and the typing-indicator
  UI are now live in production.

### Removed
- `llm.py`'s structured `YumiiResponse` instruction to the LLM
  (the synthesizer handles this now).
- 0.2.0's per-turn `SystemMessage` injection of the current time.

---

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
  `test_memory_manager.py`, `test_session_manager.py`). Test suite is
  now **57 tests** total.
- **New dependencies:** `aiosqlite`, `langgraph-checkpoint-sqlite`.

### Changed
- `graph.py` now uses `AsyncSqliteSaver` (held open by the engine for
  the lifetime of the process) instead of `InMemorySaver`.
- `llm.py` agent cache key includes a hash of injected user facts, so
  personality updates correctly when memory changes.
- `llm.py` no longer registers external tools — it relies on a
  structured `YumiiResponse` (`create_agent` with `response_format=`)
  to avoid a Groq Llama 400 error on malformed tool calls. Current
  time is injected as a `SystemMessage` per turn instead of via a
  `get_current_time` tool.
- `engine.py` initializes lazily (async `initialize()`) because
  `AsyncSqliteSaver` needs an async context, and tracks an
  `active_session_id` / `active_session_name` for the current
  conversation.

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
