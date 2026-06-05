# Yumii 🌸 — Real-Time AI Companion

[![Version](https://img.shields.io/badge/version-0.2.0-orange.svg)](CHANGELOG.md)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://python.org)
[![uv](https://img.shields.io/badge/package%20manager-uv-green.svg)](https://docs.astral.sh/uv/)
[![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Live2D](https://img.shields.io/badge/Live2D-Cubism-pink.svg)](https://www.live2d.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/CodeNeuron58/Yumii?style=social)](https://github.com/CodeNeuron58/Yumii)

Yumii is an open-source, locally-runnable AI companion with a Live2D avatar,
real-time voice conversation, and expressive personality. She runs on a standard
CPU — no expensive GPU required.

> ⚠️ **This is v0.2.0 — an alpha release.** The voice loop, avatar,
> six personalities, persistent memory, and multi-session support all work
> end-to-end. The engine will be rewritten in v1.0.0 (Triage / Planner /
> Synthesizer agent loop with tool support). **No API stability promise yet.**
> See [`CHANGELOG.md`](CHANGELOG.md) and [`ROADMAP.md`](ROADMAP.md).

---

## ⚡ Install (One Line)

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/CodeNeuron58/Yumii/master/install.ps1 | iex
```

**macOS / Linux:**
```bash
curl -LsSf https://raw.githubusercontent.com/CodeNeuron58/Yumii/master/install.sh | sh
```

**From source (developers):**
```bash
git clone https://github.com/CodeNeuron58/Yumii.git
cd Yumii
uv sync
```
Then either activate the virtual environment:
```bash
# Windows
.venv\Scripts\activate
yumii

# macOS / Linux
source .venv/bin/activate
yumii
```
Or skip activation and use:
```bash
uv run yumii
```

---

## ✨ What Yumii Does

- 🎙 **Listens** — picks up your voice using Silero VAD + Whisper (local or Groq cloud)
- 🧠 **Thinks** — responds via Groq, OpenAI, or Anthropic LLMs with a persistent personality
- 🗣 **Speaks** — synthesizes voice through ElevenLabs with real-time lip sync
- 💃 **Feels** — drives Live2D avatar expressions and motions based on emotional context
- 🧠 **Remembers** — extracts and stores user facts in local SQLite, injects them into every session
- 💬 **Sessions** — multiple independent conversations with resume, rename, and delete
- 🔐 **Private** — API keys stored in your OS keychain (Windows Credential Manager / macOS Keychain), never on disk

---

## 🚀 Quick Start

### 1. Prerequisites

- Python **3.12+**
- [`uv`](https://docs.astral.sh/uv/) (the project's package manager)

Install `uv` if you don't have it:
```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 2. Clone & Install

```bash
git clone https://github.com/CodeNeuron58/Yumii.git
cd Yumii
uv sync
```

> ⚠️ **Do NOT use `pip install`**. The project pins `torch` to a CPU-only wheel
> index. `pip` doesn't understand this and will try to download the full 2 GB
> CUDA build or fail outright. Always use `uv sync`.

### 3. Live2D Model

Yumii does **not** bundle a Live2D model. We used to ship a sample
model adapted from a third-party Live2D artist's work for the zero-config
demo, but the underlying character IP is owned by a large game company
and the artist's distribution terms explicitly prohibit redistribution.
Shipping the model in a public GitHub repo created a copyright risk for
every user who forked the project, so we removed it.

**Voice + LLM + personality all work without an avatar.** The avatar is
purely visual.

To add an avatar:

1. Download a Cubism 4 compatible Live2D model from a legal source.
   Common options: [Booth.pm](https://booth.pm/) (most original
   Live2D artists sell here), or a model whose creator has explicitly
   granted redistribution rights (rare — read the license).
2. Place the entire model folder into:
   ```
   ~/.yumii/avatar/
   ```
   *(On Windows: `C:\Users\YourName\.yumii\avatar\`)*
3. Update `modelUrl` in
   [`src/yumii/assets/webui/index.html`](src/yumii/assets/webui/index.html)
   to point at your model's `.model3.json` filename.
4. Map your model's `.exp3.json` files and motion groups to Yumii's
   emotion labels in the `EXPRESSION_MAP` and `MOTION_MAP` JavaScript
   objects in the same file. The full guide is in
   [`docs/content/customization/adding-avatars.mdx`](docs/content/customization/adding-avatars.mdx).

If you don't add a model, Yumii will still work end-to-end — she will
speak through your speakers, your mic will be heard, the LLM will
respond, but the avatar canvas will show a clear "no avatar loaded"
message instead of a character.

### 4. Configure Yumii

```bash
# Option A — activate venv (then use bare commands for the rest of the session)
.venv\Scripts\activate    # Windows
source .venv/bin/activate  # macOS / Linux
yumii

# Option B — no activation needed
uv run yumii
```

On first launch, an interactive wizard walks you through:

| Step | What it sets up |
|------|----------------|
| **Mind** | LLM provider (Groq / OpenAI / Anthropic) + API key |
| **Voice** | ElevenLabs API key + Voice ID |
| **Ears** | STT backend — Local Whisper (private, offline) or Groq Whisper (cloud, 5-10x faster) |
| **Personality** | Caring · Tsundere · Genki · Kuudere · Yandere · Dandere |

All API keys are saved to your **OS keychain** (Windows Credential Manager or macOS
Keychain) — never written to a file. You can change any setting later via the
dashboard.

### 5. Wake Up

```bash
# If venv is activated
yumii

# Without activation
uv run yumii
```

Select **🌸 Wake Yumii Up** from the dashboard. Your browser opens automatically.
Click **Connect & Start Audio Context**, allow microphone access, and start talking.

You can also manage sessions and memory directly from the CLI **before** waking Yumii up:

| Command | What it does |
|---------|-------------|
| `/chat` | Browse, resume, or delete past sessions |
| `/resume` | Resume your most recent session |
| `/sessions` | List all saved sessions |
| `/memory` | Browse and edit what Yumii remembers about you |
| `/forget` | Wipe all long-term memory (keeps sessions) |
| `/name <name>` | Rename the active session |

---

## 🎛 STT Backends

| Backend | Privacy | Speed | Requirements |
|---------|---------|-------|-------------|
| **Local Whisper** *(default)* | ✅ Fully local | ~1-2s per sentence | None |
| **Groq Whisper** | ☁️ Cloud | ~100-300ms per sentence | Free Groq API key |

Switch backends anytime via ⚙️ Configure Senses → Listening Settings.

For **Groq Whisper**: if you've already configured Groq as your LLM provider,
Yumii will reuse the same API key — no duplicate entry needed.

---

## 🤖 LLM Providers

| Provider | Model | Notes |
|----------|-------|-------|
| **Groq** *(recommended)* | llama-3.3-70b-versatile | Fastest inference, free tier |
| **OpenAI** | gpt-4o | Most capable |
| **Anthropic** | claude-3-5-sonnet | Most nuanced |

---

## 🏗 Architecture

```
  [ Microphone ]
       │
  [ Silero VAD ]  ←── Neural speech detection, 4-layer noise filtering
       │
  [ Whisper STT ]  ←── Local (CPU) or Groq Cloud
       │
  [ LangGraph Agent ] ←── AsyncSqliteSaver (persistent checkpoints)
       │
       ├── SystemMessage (personality prompt + user facts, injected every turn)
       ├── HumanMessage  (user speech)
       ├── LLM invoke    (Groq / OpenAI / Anthropic)
       └── YumiiResponse  { response_text, expression, motion }
               │
          [ ElevenLabs TTS ]
               │
          [ WebSocket ]  ──→  [ Browser ]
                                   │
                              [ Live2D Avatar ]
                                   ├── Lip sync (real-time RMS)
                                   ├── Facial expressions
                                   └── Body motions

  [ SQLite Memory ]  ←── ~/.yumii/memory/
       ├── sessions      (metadata: name, created_at, last_active)
       ├── facts         (extracted user facts, deduplicated)
       └── checkpoints   (LangGraph conversation history per session)
```

---

## 📁 Project Structure

```
src/yumii/
  agent/          # LangGraph state machine, LLM agent, personality manager
                  #   graph.py      → AsyncSqliteSaver checkpoints
                  #   llm.py        → Agent builder with fact injection
                  #   nodes.py      → chat_node with memory-aware prompts
                  #   fact_extractor.py → Automatic user-fact extraction
  api/            # FastAPI server, WebSocket, REST endpoints
                  #   server.py     → /api/sessions, /api/facts, /ws
  audio/          # STT pipeline (Silero VAD + Whisper/Groq)
  core/           # Pydantic settings, OS keychain, engine orchestrator
                  #   engine.py     → Session lifecycle + command interception
                  #   memory_db.py  → Low-level SQLite schema
                  #   memory_manager.py → Fact CRUD + extraction trigger
                  #   session_manager.py  → Session CRUD
  tts/            # ElevenLabs TTS + CAMB.ai streaming TTS
  tools/          # LangChain tools (time, etc.)
  assets/
    prompts/      # Personality prompt files (.txt)
    webui/        # Frontend HTML (Live2D + PixiJS)
  cli.py          # Typer CLI entry point (yumii command)
```

> **Avatar files** go in `~/.yumii/avatar/` (user-provided, not bundled).
> **Memory database** lives at `~/.yumii/memory/yumii.db` (auto-created).

---

## 🔐 Security

Yumii never stores API keys on disk in plaintext.
All secrets go through the [`credential_store.py`](src/yumii/core/credential_store.py)
module which delegates to your OS's native keychain:

- **Windows** → Windows Credential Manager
- **macOS** → macOS Keychain
- **Linux** → GNOME Keyring / KWallet (via libsecret)

Non-sensitive preferences (personality, provider choice) are saved to `~/.yumii/config.json`.

---

## 🤝 Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for setup instructions.

Ideas for contributions:
- New personality prompts
- Additional LangChain tools (weather, reminders, etc.)
- Alternative TTS backends (Kokoro, system TTS)
- UI/avatar improvements
- Performance optimizations

---

## 📄 License

MIT — see [LICENSE](LICENSE).
