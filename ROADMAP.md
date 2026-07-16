# 🟢 Yumii Roadmap

This document tracks what is **shipped**, what is **in progress**, and
what is **planned**. Anything not listed under "Shipped" is not in the
binary you downloaded. The "What's not in v1" section of
[`CHANGELOG.md`](CHANGELOG.md) is the authoritative list for v0.1.0.

---

## 🖥️ The desktop pivot (0.4.0 — first cut shipped, ongoing)

Yumii is moving from a browser-served Live2D page to a **native desktop app**
(Tauri) with a small floating **orb** UI you can talk to any time. The Python
brain is unchanged — the desktop app wraps it and launches it for you.

- ✅ Orb UI replaces the full-screen Live2D page; the companion/avatar mode is
  parked behind a "Coming soon" toggle.
- ✅ Tauri v2 shell: frameless, transparent, always-on-top window; system tray;
  global hotkey; launches the backend as a managed subprocess. Runs from source
  today (`cd desktop && cargo tauri dev`).
- ✅ Packaged one-click Windows installer (PyInstaller sidecar + `cargo tauri
  build` + GitHub Actions) — shipped in 0.10.0.
- ⏳ Next: the Live2D companion mode.

---

## ✅ Shipped — 0.10.0 (July 2026)

The installer release. See [`CHANGELOG.md`](CHANGELOG.md) for the full list.

- **One-click Windows installer** (setup.exe / MSI): frozen PyInstaller
  backend + Kokoro voice model bundled — no Python, no downloads, first
  run works fully offline
- **Release automation**: pushing a version tag builds the installers
  and publishes a draft GitHub Release
- **torch dropped entirely** — Silero VAD runs on onnxruntime from a
  bundled ~2.2 MB asset
- **Ollama Cloud** LLM provider (`OLLAMA_API_KEY` / `OLLAMA_MODEL`;
  `OLLAMA_BASE_URL` can target a local Ollama)
- Documentation site (Next.js) rebuilt for the product that ships
- CI: version-consistency guard + desktop shell compile job
- **132 tests** total

## ✅ Shipped — 0.9.0 (July 2026)

The companion release. See [`CHANGELOG.md`](CHANGELOG.md) for the full list.

- **Companion-grade prompts**: shared voice-first core + six
  personalities written in depth (speech patterns, emotional range,
  per-moment guidance)
- **Prefix-cache-friendly prompt assembly** (static → date → facts →
  history); the per-minute time message that broke KV caching is gone
- **Free-tier survival**: curated tool subsets, tool-result truncation,
  history windowing — requests fit 8–12k ceilings; schema sanitizer
  absorbs llama/qwen tool-calling quirks; `GROQ_MODEL` is configurable
  (default qwen3.6-27b)
- Gmail voice flow user-verified end to end (ask → approve → read aloud)
- **126 tests** total

## ✅ Shipped — 0.8.0 (July 2026)

The tools release. See [`CHANGELOG.md`](CHANGELOG.md) for the full list.

- **Composio tool integration**: connect real apps (Gmail, Calendar,
  Notion, GitHub, Slack, any toolkit slug) from the Dashboard's new
  **Tools** tab — paste a free Composio API key, click an app,
  authenticate in the browser; every tool is permission-gated (HITL)
  by default
- OAuth links open via the system browser (Tauri webviews suppress
  popups) with a clickable fallback
- Fixed a boot crash on any structured config.json value, and broken
  logging in two modules
- MCP support prototyped and parked on `feat/mcp-wiring`
- **101 tests** total

## ✅ Shipped — 0.7.0 (July 2026)

The dashboard release. See [`CHANGELOG.md`](CHANGELOG.md) for the full list.

- **Dashboard window** (gear menu / tray / `/dashboard.html`): Settings
  (providers, personality, voice, HITL, write-only API keys), Chats
  (named sessions with readable transcripts, resume / rename / delete),
  Memory (browse / edit / forget facts)
- Sessions auto-title from the first utterance; real message counts
- New REST: session transcript, session rename, validated settings API
- Fixed a Windows event-loop deadlock when opening secondary windows
- **94 tests** total

## ✅ Shipped — 0.6.0 (July 2026)

Configuration rework. See [`CHANGELOG.md`](CHANGELOG.md) for the full list.

- **File-based credentials**: API keys in `~/.yumii/auth.json` (owner-only,
  atomic writes — the Claude Code / opencode model); OS keychain and the
  `keyring` dependency removed, with automatic one-time migration
- Dependency prune: composio, composio-langchain, sounddevice, appdirs
  (85 transitive packages) removed — nothing imported them
- **91 tests** total

## ✅ Shipped — 0.5.0 (July 2026)

Local voice release. See [`CHANGELOG.md`](CHANGELOG.md) for the full list.

- **Kokoro-82M local TTS** — fully offline voice on CPU (ONNX, no torch,
  no API key), 54 voices, recommended default in the setup wizards
- Reply-to-speech latency cut from ~4 s to ~0.8–1.5 s (pacing-aware
  incremental synthesis + startup warmup)
- **Vosk offline streaming STT** with live word-by-word partials (opt-in,
  flagged low-accuracy)
- Real session resume over WebSocket; reconnects no longer create junk
  sessions; CLI `/resume` deep-links the session
- Security: CORS wildcard replaced with a local-frontend allowlist + WS
  origin gate (closes drive-by localhost reads of `/api/facts`)
- Stability sweep: STT off the event loop, per-turn message IDs,
  disconnect handling, UTF-8-safe logging, ElevenLabs PCM streaming
- **85 tests** total, verified against a live server

## ✅ Shipped — 0.3.0 (June 2026)

Streaming engine fix + prompt label-leak fix on top of the
agentic-loop work. Pre-1.0 — APIs may change. See
[`CHANGELOG.md`](CHANGELOG.md) for the full list.

- Custom `StateGraph` + `ToolNode` agent loop (replaces `create_agent`)
- Tool registry, `ToolPolicy` protocol, MCP config loader
- Heuristic emotion / motion synthesizer (replaces structured-output
  LLM call)
- Streaming engine events + ElevenLabs streaming TTS
- HITL confirmation gate (mode = `never` / `external` / `always`)
- Web search tool (DuckDuckGo), gated by default
- **184 tests** total — 7 new test modules since 0.2.0

## ✅ Shipped — 0.2.0 (June 2026)

Memory & Sessions release. **Alpha — no API stability promise.** See
`CHANGELOG.md` for the full list.

- Persistent SQLite memory: `yumii.db` (sessions), `store.db` (user
  facts via LangGraph `AsyncSqliteStore`), `checkpoints.db` (LangGraph
  `AsyncSqliteSaver` conversation history, per-session `thread_id`)
- Automatic fact extraction from every conversation turn
  (Groq 8b / OpenAI mini / Anthropic Sonnet), substring-deduplicated
- Session lifecycle: create, resume, rename, list, archive, delete
- CLI commands: `/chat`, `/resume`, `/sessions`, `/memory`,
  `/forget`, `/name`, plus `yumii resume-chat` / `delete-session` /
  `forget` direct subcommands
- In-conversation voice commands (`/new`, `/resume`, `/name`, etc.)
  routed via WebSocket JSON `command` frames
- REST API: `GET/POST /api/sessions`, `POST /api/sessions/{id}/resume`,
  `DELETE /api/sessions/{id}`, `GET/PUT/DELETE /api/facts[/{id}]`,
  `GET /api/config`
- Engine refactor: lazy async `initialize()`, `active_session_id`
  + `active_session_name`, queue drain on session switch
- Removed dead frontend session/memory UI scaffolding
- 4 new test modules (`test_fact_extractor`, `test_memory_db`,
  `test_memory_manager`, `test_session_manager`) — **57 tests** total

## ✅ Shipped — 0.1.0 (June 2026)

The first public release.

- Real-time voice loop (Silero VAD → STT → LangGraph → TTS)
- Live2D avatar with LLM-driven expressions and motions
- Six personalities (caring, tsundere, genki, kuudere, yandere, dandere)
- Barge-in / speech interruption
- Three LLM providers (Groq, OpenAI, Anthropic)
- Two STT backends (local Whisper, Groq Whisper)
- Two TTS backends (ElevenLabs, CAMB.ai)
- OS-keychain credential storage
- Polished Typer + Rich CLI
- One-line installers for Windows and macOS / Linux
- 24 unit tests + ruff-clean code

---

## 🚧 In progress — v1.0 (target: Q3 2026)

The next release. Focus: **declaring the architecture stable** so
downstream code can rely on the public API (tool registry,
`YumiiResponse` shape, WebSocket event protocol,
`engine.request_confirmation`) without breakage.

Note: the original v1.0 plan called for a 3-stage
**Triage / Planner / Synthesizer** agent loop. We abandoned that
design in favor of a simpler custom `StateGraph` + `ToolNode`
(shipped in 0.3.0) which is less code, more direct, and easier to
test. The "Synthesizer" half of the original plan survives as the
heuristic `synthesize()` classifier in 0.3.0; the Triage and
Planner pre-pass stages were *not* built and *will not* be built
— they are part of an abandoned design, not a backlog.

- **`ToolContract` protocol.** A new tool is added in <30 lines:
  Pydantic input schema, an `async run()` method, a
  `requires_confirmation` flag, and an idempotency key. *Shipped
  in 0.3.0 as `ToolPolicy` (no `async run()` envelope; tools remain
  LangChain-native).*
- **Confirmation gates.** Side-effecting tools pause the engine and
  emit a `{"type": "confirmation_request"}` WebSocket event.
  *Shipped in 0.3.0.*
- **MCP server transport.** Expose the tool registry over the Model
  Context Protocol so Claude Desktop, Cursor, etc. can call Yumii's
  tools. *Partial in 0.3.0 — client-side loader (MCP servers → Yumii
  tools) is in. The server-side (Yumii tools → external MCP clients)
  is still pending.*
- **A first real integration.** Likely Google Calendar (read-only)
  or Google Tasks.
- **More tests.** Aim for 60% coverage of `core/` and `agent/`.
  *184 tests in 0.3.0, but coverage % not yet measured.*

---

## 🧠 Planned — v2.0 (target: Q4 2026)

The flagship release. Focus: **agentic capabilities**.

- **Multimodal vision input.** Webcam or screen-share as visual
  context. Uses a multimodal LLM (Llama-3.2-Vision, GPT-4o, or
  Claude 3.5 Sonnet).
- **Local TTS (Kokoro or similar).** A fully offline TTS provider
  for users who don't want to depend on ElevenLabs or CAMB.ai.
  *Shipped in 0.5.0 (Kokoro-82M). A second local provider with voice
  cloning (NeuTTS Nano) is under consideration.*
- **Proactive reach-outs.** Yumii is currently 100% reactive. The
  vision is for her to occasionally check in unprompted ("It's been
  a long day — how are you holding up?"). This requires a scheduler
  and a permission model, both of which are open design questions.

---

## 🗑️ Explicitly NOT planned

- A cloud-hosted / SaaS Yumii that keeps your data on a server. The whole
  point is local and private.
- Closed-source. The project's value is that every line of the brain is editable.
- A mobile app. Yumii is going desktop-first (Tauri); a phone app would be a
  different project.

---

*Want to help? See [`CONTRIBUTING.md`](CONTRIBUTING.md) and grab an
issue tagged with the milestone you want to contribute to.*
