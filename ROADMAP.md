# 🌸 Yumii Roadmap

This document tracks what is **shipped**, what is **in progress**, and
what is **planned**. Anything not listed under "Shipped" is not in the
binary you downloaded. The "What's not in v1" section of
[`CHANGELOG.md`](CHANGELOG.md) is the authoritative list for v0.1.0.

---

## ✅ Shipped — 0.2.0 (June 2026)

Memory & Sessions release. **Alpha — no API stability promise.** See
`CHANGELOG.md` for the full list.

- Persistent SQLite memory (sessions + user facts + LangGraph checkpoints)
- Automatic fact extraction from conversation turns
- Session management (create, resume, rename, list, delete)
- CLI commands: `/chat`, `/resume`, `/sessions`, `/memory`, `/forget`, `/name`
- In-conversation voice commands (`/new`, `/resume`, `/sessions`, etc.)
- REST API for sessions and facts
- 4 new test modules (48 total tests)

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

The next release. Focus: **agentic loop**.

- **Triage / Planner / Synthesizer agent loop.** A cheap classifier
  (Triage) produces an immediate spoken acknowledgement, the Planner
  builds a `Plan` of tool calls, the Tool Dispatcher runs them with
  cancellation support, and the Synthesizer produces the final
  spoken answer.
- **`ToolContract` protocol.** A new tool is added in <30 lines:
  Pydantic input schema, an `async run()` method, a
  `requires_confirmation` flag, and an idempotency key.
- **Confirmation gates.** Side-effecting tools pause the engine and
  emit a `{"type": "confirmation_request"}` WebSocket event.
- **MCP server transport.** Expose the tool registry over the Model
  Context Protocol so Claude Desktop, Cursor, etc. can call Yumii's
  tools.
- **A first real integration.** Likely Google Calendar (read-only)
  or Google Tasks.
- **More tests.** Aim for 60% coverage of `core/` and `agent/`.

---

## 🧠 Planned — v2.0 (target: Q4 2026)

The flagship release. Focus: **agentic capabilities**.

- **Multimodal vision input.** Webcam or screen-share as visual
  context. Uses a multimodal LLM (Llama-3.2-Vision, GPT-4o, or
  Claude 3.5 Sonnet).
- **Local TTS (Kokoro or similar).** A fully offline TTS provider
  for users who don't want to depend on ElevenLabs or CAMB.ai.
  Currently in research.
- **Proactive reach-outs.** Yumii is currently 100% reactive. The
  vision is for her to occasionally check in unprompted ("It's been
  a long day — how are you holding up?"). This requires a scheduler
  and a permission model, both of which are open design questions.

---

## 🗑️ Explicitly NOT planned

- A web-only no-install version of Yumii. The whole point is local.
- Closed-source cloud-hosted Yumii. The project's value is that
  every line of the brain is editable.
- A mobile app. The browser-based Live2D client works on mobile
  browsers; a native app would be a different project.

---

*Want to help? See [`CONTRIBUTING.md`](CONTRIBUTING.md) and grab an
issue tagged with the milestone you want to contribute to.*
