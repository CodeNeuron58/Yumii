# Changelog

All notable changes to Yumii will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.10.0] — 2026-07-15

The installer release. Yumii becomes a real Windows app: download one
setup.exe, install, talk — no Python, no model downloads, no terminal.
The frozen backend and the Kokoro voice model ship inside the
installer, so the first run works fully offline. Under the hood, torch
is gone entirely (Silero VAD now runs on onnxruntime from a ~2 MB
bundled asset) and Ollama Cloud joins the LLM provider list.

### Added
- **Windows installer** (NSIS `setup.exe` + MSI): the backend is frozen
  with PyInstaller (onedir) and bundled as a Tauri resource together
  with the Kokoro fp32 model, so a fresh install needs no Python, no
  downloads, and no setup — the shell launches the bundled sidecar and
  points it at the bundled models via `YUMII_MODELS_DIR`. Build recipe:
  `fetch_models.py` → `pyinstaller yumii-server.spec` → `tauri build
  --config tauri.bundle.conf.json`.
- **Release workflow** (GitHub Actions): pushing a `v*` tag builds the
  installers and publishes them to a **draft** GitHub Release — nothing
  goes public until the build is reviewed and the release is published.
- **Ollama Cloud LLM provider**: `OLLAMA_API_KEY` + a cloud model name
  (default `gpt-oss:120b`); `OLLAMA_BASE_URL` can point at a local
  Ollama instead for a fully offline mind. Free-text model field in the
  Dashboard.
- **Documentation site** (`docs/`, Next.js + MDX): installation, first
  conversation, guides (talking, personalities, memory, tools,
  dashboard), provider setup, CLI/API/settings reference,
  troubleshooting — rebuilt to describe the product that actually
  ships.

### Changed
- **torch dropped entirely.** Silero VAD runs on onnxruntime from a
  bundled ~2.2 MB ONNX asset (was: `torch.hub` download of the same
  model, dragging in hundreds of MB of torch/torchaudio). Same v5
  model, same probabilities, no first-run download.
- **LLM provider clients build lazily** — importing the agent no longer
  requires an API key to exist (fixed crashing imports on fresh clones
  and in CI).

### CI
- **Version-consistency guard**: `pyproject.toml`,
  `tauri.conf.json`, and `Cargo.toml` must agree on the version or CI
  fails (they drifted once — a packaged app almost shipped labelled
  v0.1.0).
- **Desktop shell compile job** (Windows) so Rust breakage is caught on
  every push, not at release time.

### Notes
- **132 tests.** The installer is not code-signed yet — Windows
  SmartScreen shows "Windows protected your PC" on first run; that's
  expected for any unsigned installer (More info → Run anyway).

## [0.9.0] — 2026-07-08

The companion release. Yumii's entire prompt stack is rewritten to
companion grade — a shared core (voice-first speaking rules, natural
memory use, tool etiquette, honesty boundaries) plus six personalities
written in real depth — and the agent now survives free-tier reality:
requests stay under provider ceilings, sloppy third-party tool schemas
are sanitized, and a malformed tool call degrades to a spoken apology
instead of a crashed turn. The Gmail voice flow (ask → permission
popup → fetch → read aloud) is user-verified end to end.

### Added
- **Companion core prompt** (`assets/prompts/_core.txt`): identity,
  strict spoken-voice rules (no markdown/lists/symbols — everything is
  TTS'd; numbers and emails read naturally; short by default), memory
  woven like a friend instead of recited, HITL tool etiquette, honesty
  and care boundaries. Stated once for all personalities.
- **Six personalities rewritten in depth**: essence, speech patterns
  with example lines, emotional range mapped to the synthesizer's
  expression set, and per-moment guidance (greetings, user sadness,
  successes, permission denials, not knowing). Yandere gets explicit
  safety rails — theatrical devotion, never controlling.
- **`GROQ_MODEL` setting** (config.json / env). Default is
  `qwen/qwen3.6-27b` after live testing: cleaner tool calls than
  llama-3.3-70b and a separate free-tier quota bucket. One config line
  switches back.
- **Bind-time tool schema sanitizer**: null-defaulted fields become
  nullable, booleans also accept strings — absorbing both llama's
  explicit-null habit and qwen's Python-cased XML booleans, which
  Groq's strict server-side validation otherwise rejects as
  `tool_use_failed` even when the call is semantically perfect.

### Changed
- **Prompt assembly is prefix-cache friendly**: ordered [static core +
  personality] → [date] → [facts] → [history] → [new message]. The old
  per-turn "current time is 11:42 PM" message sat before the entire
  history and broke provider KV caching every minute; the date now
  changes once a day and precise time is a tool call. ~1.8k tokens of
  always-cacheable static prefix.
- **Request-size guards** (free tiers cap single requests at 8–12k
  tokens): Composio toolkits load curated tool subsets (Gmail: fetch +
  send — a full toolkit is ~10k tokens of schema per request,
  measured); tool results truncate at 3k chars before entering the
  checkpointed history; the LLM request carries the last 12 messages
  (the checkpoint keeps everything).
- A `tool_use_failed` generation retries once, then degrades to a
  spoken apology instead of surfacing an error.

### Notes
- Test suite is 126 tests. Free-tier budgets are deliberately tight;
  on a paid tier the three constants (curation width, result cap,
  history window) can simply be raised.

## [0.8.0] — 2026-07-07

The tools release. Yumii gets hands: connect your real apps (Gmail,
Calendar, Notion, GitHub, Slack, …) through Composio and ask her to use
them — with her asking permission before every action. The full flow
runs inside the app: paste a free Composio API key, click an app,
authenticate in the browser, restart, talk.

### Added
- **Composio tool integration.** A new **Tools** tab in the Dashboard:
  quick-connect buttons for popular apps plus any toolkit slug, a
  connected-apps list with disable, and key status. Connecting an app
  mints Composio's OAuth link (`auth_configs.create` +
  `connected_accounts.link` — the post-`initiate`-retirement flow) and
  opens it in the system browser; Composio holds the tokens.
- `composio_loader.py`: on startup, tools for every enabled toolkit are
  fetched and registered **EXTERNAL + confirmation-gated** — every
  Composio tool triggers the HITL prompt until the user relaxes
  `HITL_MODE`. SDK calls run off the event loop with timeouts; a bad
  key or dead network logs a warning and never blocks boot.
- `COMPOSIO_API_KEY` as a first-class credential (Settings → API Keys,
  stored in `auth.json`), read fresh so paste-key → connect-app works
  without a restart. Enabled toolkits live under `COMPOSIO_TOOLKITS`
  in `config.json`.
- REST: `GET /api/composio/status`, `POST /api/composio/connect`,
  `DELETE /api/composio/toolkits/{slug}`.
- Dependencies pinned to the battle-tested line (`composio>=0.13,<0.14`)
  — the 1.0 series changes the call shapes this integration relies on.

### Fixed
- **Configuring any structured value in config.json crashed the app at
  boot** — every config value was pushed into `os.environ`, which
  rejects non-strings. Present since 0.3.0; only scalar strings are
  exported now.
- Two modules (`mcp_config`, tool `registry`) logged structlog-style
  keyword args through stdlib loggers, raising `TypeError` on their
  first real log line.
- OAuth links opened via `window.open()` never appeared — popups are
  silently suppressed inside the Tauri webview. The backend now opens
  the system browser itself, with a clickable fallback link in the
  dashboard.

### Notes
- Test suite is 101 tests. The in-app connect flow (key → Gmail →
  browser OAuth → success) is user-verified end to end; MCP support
  was prototyped and parked on the `feat/mcp-wiring` branch in favour
  of Composio.

## [0.7.0] — 2026-07-07

The dashboard release. The orb stays a pure ambient presence; managing
Yumii — settings, conversations, memory — moves into a proper second
window instead of terminal wizards. Conversations finally become
recognisable: sessions title themselves and message counts are real.

### Added
- **Dashboard window** (`dashboard.html`) with three tabs, opened from the
  orb's gear menu, the system tray, or `/dashboard.html` in browser mode:
  - **Settings** — LLM / TTS / STT provider, personality, Whisper model
    size, Kokoro voice, and tool-confirmation (HITL) mode. API keys are
    entered write-only with a masked "current" display and stored in
    `auth.json`. The UI distinguishes live changes (personality applies on
    the next reply) from ones needing a restart (providers, keys).
  - **Chats** — every conversation with its real name, date, and message
    count; readable transcript (tool usage shown as small events); Resume
    (switches the live engine — the next thing you say continues that
    conversation), Rename, and Delete.
  - **Memory** — browse, edit, or forget every fact Yumii has extracted.
- **Sessions auto-title** from your first utterance, and `message_count`
  is finally incremented (every session used to be "New Chat · 0 msg").
- **New REST endpoints:** `GET /api/sessions/{id}/messages` (transcript
  read from the LangGraph checkpoint), `PUT /api/sessions/{id}` (rename —
  previously impossible anywhere), and `GET/PUT /api/settings` (validated
  against an allowlist of keys and choices; unknown keys rejected).
- Tray menu gains a **Dashboard** entry.

### Fixed
- Opening the dashboard **deadlocked the entire app on Windows** (blank
  window, dead close button, Quit unresponsive): the gear/tray handlers
  run on the main event loop, and creating a webview window from there
  blocks on an event the busy loop can never process. Window creation now
  runs off the event loop.
- The dashboard shows a "waking up" notice and retries while the backend
  is still booting, instead of rendering a blank page.

### Notes
- Test suite is 94 tests; endpoints and the auto-naming flow were
  verified against a live server (a real voice turn titled its own
  session and its transcript read back correctly).

## [0.6.0] — 2026-07-07

Configuration rework. API keys move out of the OS keychain into a plain,
owner-only file — the same model Claude Code and opencode use — making
credentials visible, portable, and editable, and clearing the path for the
planned in-app settings UI. Plus a dependency prune.

### Changed
- **Credentials live in `~/.yumii/auth.json`** (owner-only permissions,
  atomic tmp+rename writes), not the OS keychain. The keychain was a
  packaging and portability tax: keyring backends misbehave on
  Linux/headless, the entries are invisible to users, and a settings GUI
  wants a file it can read and write. `credential_store.py` keeps the same
  public API, so the CLI wizards and config loading work unchanged.
- A corrupt `auth.json` is set aside as `auth.json.corrupt` instead of being
  clobbered by the next save, and `load_all()` only accepts known credential
  keys — a hand-edited file can't inject arbitrary environment variables at
  startup.

### Removed
- **`keyring` dependency.** Upgrading installs migrate automatically: if
  `auth.json` doesn't exist yet and the keyring package is still importable,
  legacy keychain entries are copied over on first run. The keychain entries
  themselves are left in place — remove them via your OS's credential
  manager (Windows: Control Panel → Credential Manager → Windows
  Credentials → entries named "Yumii").
- Four dependencies nothing imported (85 transitive packages): `composio`
  and `composio-langchain` (added ahead of an integration that hasn't
  started — will return when it does), `sounddevice` (the mic has come from
  the browser/webview for a long time), and `appdirs`.

### Notes
- Test suite is 91 tests; the release was verified against a live server
  running with keyring absent from the environment.

## [0.5.0] — 2026-07-07

Local voice release. Yumii's voice now runs fully offline (Kokoro-82M on
CPU, no API key) with reply-to-speech latency cut from ~4 s to ~0.8–1.5 s,
an offline streaming STT option (Vosk) shows your words as you say them,
sessions actually resume, and a security sweep closes a localhost
data-exfiltration hole. 85 tests, all green; the fixes below were verified
against a live server.

### Added
- **Kokoro local TTS** (`tts/kokoro_speaker.py`). Fully offline TTS on CPU
  via ONNX Runtime — no API key, no cloud, no torch. Model files (~350 MB)
  download to `~/.yumii/models/kokoro` on first use. 54 built-in voices
  (`KOKORO_VOICE`, default `af_heart`) with a curated picker in both CLI
  wizards; listed first as the recommended provider. fp32 is the default
  variant: int8 measured ~3.7× *slower* than fp32 on x86 (quantized ops
  hit onnxruntime fallback kernels).
- **Vosk offline streaming STT** (`audio/vosk_provider.py`). Third STT
  backend — fully offline, with word-by-word partial transcripts rendered
  live in the orb card. Flagged low-accuracy / not recommended; opt-in.
- **Real session resume over WebSocket.** The frontend sends a
  `session_select` frame (`new` / `resume` / `auto`) as its first WS
  message; `auto` keeps the active session across reconnects. The CLI's
  `/resume` and `/chat` deep-link the browser with `?session=<id>`, so
  resuming actually resumes.
- `YUMII_ALLOWED_ORIGINS` env var plus server-side logging of rejected
  origins (`http_origin_not_allowlisted` / `ws_origin_rejected`), so an
  allowlist miss is self-diagnosing instead of a silent client-side CORS
  failure.

### Changed
- **Reply-to-speech latency cut from ~4 s to ~0.8–1.5 s** (Kokoro).
  Replies split at sentence / clause / conjunction boundaries and
  synthesize incrementally under a pacing budget — a small first chunk so
  the voice starts fast, later chunks capped so synthesis stays ahead of
  playback and never stalls mid-reply. The ONNX session warms up in the
  background at startup so the first real reply doesn't pay the ~30%
  cold-run penalty.
- **STT no longer blocks the event loop.** Whisper inference / the Groq
  HTTP call run in a worker thread; the WebSocket, TTS streaming, and
  barge-in stay responsive during transcription.
- ElevenLabs streaming now requests `pcm_22050` instead of MP3 — the orb
  frontend decodes streamed chunks as raw PCM16, so the MP3 stream played
  as static.
- Dropped Groq STT segments now log at `info` (`stt_dropped` + reason), so
  a discarded utterance is distinguishable from a slow one.
- Log streams forced to UTF-8 (`errors="replace"`); Unicode in a log line
  no longer raises `UnicodeEncodeError` on Windows consoles or redirected
  output. The Tauri sidecar also sets `PYTHONIOENCODING=utf-8`.

### Fixed
- **A new session was created on every WebSocket reconnect** (one per 3 s
  retry) — the orb frontend never negotiated a session, so history was
  unreachable and the sessions table filled with junk. See "Real session
  resume" above.
- **Repeated identical utterances corrupted history.** Message IDs were
  derived from `hash(user_input)`, so saying "yes" twice made LangGraph's
  `add_messages` reducer overwrite the earlier entry instead of appending.
  IDs are now scoped to a per-turn UUID.
- **Voice personality switching ignored punctuation.** "Switch to
  tsundere." (with STT punctuation) never matched the detector; input is
  normalized before matching, with regression tests.
- **Every client disconnect raised `RuntimeError`** ("Cannot call
  'receive' once a disconnect message has been received") — Starlette
  returns the disconnect message rather than raising, and the WS loop
  called `receive()` again.
- `PUT /api/facts/{id}` with a missing field returned HTTP 200 with a
  tuple-shaped body; now a proper 400.
- The Tauri **dev-mode** webview couldn't connect after the security
  hardening below: `tauri dev` serves the frontend from its own local
  static server (port 1430), not `tauri://localhost`. Dev origins are now
  allowlisted.

### Security
- **CORS wildcard removed.** `allow_origins=["*"]` let any website the
  user visits read `/api/facts` (personal memory) and manage sessions off
  `127.0.0.1`. Requests are now restricted to an allowlist of Yumii's own
  frontends (localhost:8000 and the Tauri webview / dev-server origins),
  and WebSocket handshakes from foreign browser origins are rejected
  with 403.

## [0.4.0] — 2026-07-02

Desktop pivot — first cut. Moves from a browser-served Live2D page to a native
**desktop app** (Tauri) with a small floating **orb** UI, and stops the cloud
STT path from transcribing non-speech. The Python brain (engine, agent, audio,
memory) is otherwise unchanged — the desktop app wraps it.

### Added
- **Orb UI.** New single-file frontend (`src/yumii/assets/webui/index.html`):
  a floating orb with idle / listening / thinking / speaking states, emotion
  tint, and audio-driven pulse. Reuses the existing WebSocket, mic capture,
  streaming-audio, interrupt, status-bar, and HITL-confirmation plumbing. A mode
  selector shows a **"Coming soon"** panel for the companion/avatar mode.
- **Tauri v2 desktop shell** (`desktop/src-tauri/`). Frameless, transparent,
  always-on-top orb window with a system tray (Show/Hide, Quit) and a
  Ctrl+Shift+Space global hotkey. Launches the Python backend
  (`python -m yumii server`) as a managed subprocess and stops it on exit.
- **`GET /health`** endpoint for readiness polling (used by the orb boot flow
  and the desktop shell before connecting the WebSocket).

### Changed
- The full-screen Live2D + PixiJS UI is replaced by the orb. The previous UI is
  archived (not served) as
  `src/yumii/assets/webui/_companion_live2d.reference.html` for the future
  companion mode.

### Fixed
- **Cloud STT no longer transcribes humming / noise.** The Groq Whisper path
  accepted whatever text Whisper returned, so humming, singing, and background
  noise got transcribed and answered. It now requests `verbose_json` and drops
  low-confidence / non-speech segments (`no_speech_prob > 0.6`,
  `avg_logprob < -1.0`, `compression_ratio > 2.4`) — mirroring the guard the
  local path already had. VAD energy floor nudged up (`RMS_ENERGY_GATE`
  0.008 → 0.012) so faint background doesn't start a capture.

### Notes
- The desktop app currently runs from source (`cd desktop && cargo tauri dev`);
  a packaged one-click installer is not built yet.

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
