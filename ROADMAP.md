# 🌸 Yumi Roadmap

This document tracks what is **shipped**, what is **in progress**, and
what is **planned**. Anything not listed under "Shipped" is not in the
binary you downloaded. The "What's not in v1" section of
[`CHANGELOG.md`](CHANGELOG.md) is the authoritative list for v0.1.0.

---

## ✅ Shipped — 0.1.0 (June 2026)

The first public release. **Alpha — no API stability promise.** See
`CHANGELOG.md` for the full list. The next release is v1.0.0, which
will be tagged once the Triage / Planner / Synthesizer agent loop,
persistent memory, and tool registry are all in place.

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

## 🚧 In progress — v1.1 (target: Q3 2026)

The next release. Focus: **memory**.

- **Persistent conversation log.** Append every turn to a SQLite
  database at `~/.yumi/memory/conversations.db`. The log survives
  server restarts. No vector store yet — keyword matching.
- **User-facts table.** A `UserFacts` table stores small extracted
  facts ("user is vegetarian", "user's timezone is IST"). Populated
  by a periodic extraction step (likely an LLM pass at the end of
  each session).
- **Per-WebSocket session IDs.** The current `yumi_session_1`
  hardcoded thread becomes per-connection, so multiple browser tabs
  no longer share conversation history.
- **A `/forget-me` CLI command** that wipes the local memory store,
  for users who want a clean slate.
- **More tests.** Aim for 60% coverage of `core/` and `agent/`.
  The v1.0 tests are sanity checks, not a full suite.

---

## 🧠 Planned — v2.0 (target: Q4 2026)

The flagship release. Focus: **agentic capabilities**.

- **Triage / Planner / Synthesizer agent loop.** A cheap classifier
  (Triage) produces an immediate spoken acknowledgement, the Planner
  builds a `Plan` of tool calls, the Tool Dispatcher runs them with
  cancellation support, and the Synthesizer produces the final
  spoken answer. This is the architecture described in the project
  wiki and the v2 design notes.
- **`ToolContract` protocol.** A new tool is added in <30 lines:
  Pydantic input schema, an `async run()` method, a
  `requires_confirmation` flag, and an idempotency key.
- **Confirmation gates.** Side-effecting tools (anything that
  changes the world — sends email, books, orders) pause the engine
  and emit a `{"type": "confirmation_request"}` WebSocket event.
  The frontend shows a "Yumi wants to do X. Approve?" overlay.
  Voice + button both work.
- **MCP server transport.** Once the tool registry exists, expose it
  over the Model Context Protocol so Claude Desktop, Cursor, and
  other clients can call Yumi's tools.
- **A first real integration.** Likely Google Calendar (read-only)
  or Google Tasks — both have clean OAuth flows, real value, and no
  legal grey area.

---

## 🎨 Planned — post v2.0

- **Multimodal vision input.** Webcam or screen-share as visual
  context. Uses a multimodal LLM (Llama-3.2-Vision, GPT-4o, or
  Claude 3.5 Sonnet).
- **Local TTS (Kokoro or similar).** A fully offline TTS provider
  for users who don't want to depend on ElevenLabs or CAMB.ai.
  Currently in research.
- **Proactive reach-outs.** Yumi is currently 100% reactive. The
  vision is for her to occasionally check in unprompted ("It's been
  a long day — how are you holding up?"). This requires a scheduler
  and a permission model, both of which are open design questions.

---

## 🗑️ Explicitly NOT planned

- A web-only no-install version of Yumi. The whole point is local.
- Closed-source cloud-hosted Yumi. The project's value is that
  every line of the brain is editable.
- A mobile app. The browser-based Live2D client works on mobile
  browsers; a native app would be a different project.

---

*Want to help? See [`CONTRIBUTING.md`](CONTRIBUTING.md) and grab an
issue tagged with the milestone you want to contribute to.*
