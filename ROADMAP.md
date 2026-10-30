# Yumii Roadmap

This document tracks what is **shipped**, what is **in progress**, and
what is **planned**. Anything not listed under "Shipped" is not in the
binary you downloaded. The "What's not in v1" section of
[`CHANGELOG.md`](CHANGELOG.md) is the authoritative list for v0.1.0.

---

## ✅ Shipped — 0.15.0 (October 2026)

The Nemotron release (built during the Nebius x NVIDIA Global AI Hackathon).
See [`CHANGELOG.md`](CHANGELOG.md) for the full list.

- **NVIDIA Nemotron on Nebius Token Factory** is the default mind —
  Nemotron 3 Super for conversation and tools, Nemotron 3 Nano for
  background memory work; reasoning off for voice latency; cold-start warm-up
- **Companion-grade prompts, measured** on a scripted conversation suite:
  shorter spoken replies, fewer stacked questions, honest answers, healthy
  goodbyes; emojis/markdown never spoken (cleaned in code)
- **Tavily web search**; new experimental ears (NVIDIA Nemotron Speech,
  Moonshine); installer onboarding wizard; **the island** — a new
  top-of-screen UI and dashboard, with tool approvals answered by voice
- **Provider registry** for speech and voice; a long list of fixes
- **531 tests** total

## ✅ Shipped — 0.14.0 (October 2026)

The voice release: token-to-speech streaming (~4 s → ~1 s to first word),
real barge-in, Smart Turn v3 end-of-turn detection, the 12-provider model
picker, session continuity across restarts, typed input + voice commands,
memory that works on every provider.

## ✅ Shipped — 0.13.0 (July 2026)

The polish release: native web search, a refined orb, an installer that
works on locked-down Windows, a leaner codebase.

## ✅ Shipped — 0.12.0 (July 2026)

The first-run release — the experimental preview: first-launch onboarding
with model download progress, actionable error cards instead of silent
freezes, Whisper models mirrored on GitHub, a backend that survives a taken
port, DNS-rebinding protection.

## ✅ Shipped — 0.11.0 (July 2026)

The one-command release: `iex (irm https://yumii.me/install.ps1)` (uv +
PyPI + an 8 MB desktop shell), searchable memory (FTS5), agent-written
memory, session summaries with a sense of time, mic mute, Ollama Cloud.

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

## Next up

- **Proactiveness, done properly.** Yumii is still 100% reactive. The
  research (mixed-initiative HCI, interruptibility studies, ProactiveBench,
  and how ChatGPT Pulse, OpenClaw and companion apps fared) points to one
  design: reminders and routines you ask for first; things she infers become
  *offers* ("want me to check in after your exam?"); deterministic checks
  before she ever speaks (fullscreen, presentation, focus mode, mute, quiet
  hours, cooldowns); a cheap "should I speak?" pass whose default is
  silence; gentle delivery; full user control; and no guilt-trip messages.
- **Seeing your screen.** Experimental, opt-in per session — she can look
  at what you're looking at and help with it, using a multimodal model
  (Nemotron 3.5 Super VL is a candidate).
- **The desktop pet.** A pixel-art companion skin that sits on the taskbar
  and talks in a thought bubble, beside the island.

---

## Later

- **Direct MCP and tool integrations**, beyond Composio.
- **macOS and Linux desktop shells.**
- **More voices, personalities, and languages.**
- **Deeper, honest emotional support** grounded in real psychology.
- **Live2D avatar mode.** The long-term dream — no timeline yet.

---

## Explicitly NOT planned

- A cloud-hosted / SaaS Yumii that keeps your data on a server. The whole
  point is local and private.
- Closed-source. The project's value is that every line of the brain is editable.
- A mobile app. Yumii is going desktop-first (Tauri); a phone app would be a
  different project.

---

*Want to help? See [`CONTRIBUTING.md`](CONTRIBUTING.md) and grab an
issue tagged with the milestone you want to contribute to.*
