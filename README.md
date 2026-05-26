# Yumi 🌸 — Real-Time AI Companion

[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://python.org)
[![uv](https://img.shields.io/badge/package%20manager-uv-green.svg)](https://docs.astral.sh/uv/)
[![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Live2D](https://img.shields.io/badge/Live2D-Cubism-pink.svg)](https://www.live2d.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Yumi is an open-source, locally-runnable AI companion with a Live2D avatar,
real-time voice conversation, and expressive personality. She runs on a standard
CPU — no expensive GPU required.

---

## ✨ What Yumi Does

- 🎙 **Listens** — picks up your voice using Silero VAD + Whisper (local or Groq cloud)
- 🧠 **Thinks** — responds via Groq, OpenAI, or Anthropic LLMs with a persistent personality
- 🗣 **Speaks** — synthesizes voice through ElevenLabs with real-time lip sync
- 💃 **Feels** — drives Live2D avatar expressions and motions based on emotional context
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
git clone https://github.com/yourusername/yumi.git
cd yumi
uv sync
```

> ⚠️ **Do NOT use `pip install`**. The project pins `torch` to a CPU-only wheel
> index. `pip` doesn't understand this and will try to download the full 2 GB
> CUDA build or fail outright. Always use `uv sync`.

### 3. Live2D Model

Yumi's avatar uses the Live2D Cubism SDK. Due to licensing, the model file is not
bundled in this repo.

1. Browse [Booth.pm](https://booth.pm/) for a Cubism 4 compatible Live2D model.
2. Download and extract it.
3. Place the entire model folder into:
   ```
   src/yumi/Yumi_Avatar/
   ```
4. Update `modelUrl` in [`src/yumi/webui/index.html`](src/yumi/webui/index.html#L111)
   to point to your model's `.model3.json` file.

### 4. Configure Yumi

```bash
uv run yumi
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
uv run yumi
```

Select **🌸 Wake Yumi Up** from the dashboard. Your browser opens automatically.
Click **Connect & Start Audio Context**, allow microphone access, and start talking.

---

## 🎛 STT Backends

| Backend | Privacy | Speed | Requirements |
|---------|---------|-------|-------------|
| **Local Whisper** *(default)* | ✅ Fully local | ~1-2s per sentence | None |
| **Groq Whisper** | ☁️ Cloud | ~100-300ms per sentence | Free Groq API key |

Switch backends anytime via ⚙️ Configure Senses → Listening Settings.

For **Groq Whisper**: if you've already configured Groq as your LLM provider,
Yumi will reuse the same API key — no duplicate entry needed.

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
  [ LangGraph Agent ]
       │
       ├── SystemMessage (personality prompt, injected every turn)
       ├── HumanMessage  (user speech)
       ├── LLM invoke    (Groq / OpenAI / Anthropic)
       └── YumiResponse  { response_text, expression, motion }
               │
          [ ElevenLabs TTS ]
               │
          [ WebSocket ]  ──→  [ Browser ]
                                   │
                              [ Live2D Avatar ]
                                   ├── Lip sync (real-time RMS)
                                   ├── Facial expressions
                                   └── Body motions
```

---

## 📁 Project Structure

```
src/yumi/
  agent/          # LangGraph state machine, LLM agent, personality manager
    prompts/      # Personality prompt files (.txt)
  api/            # FastAPI server, WebSocket broadcast
  audio/          # STT pipeline (Silero VAD + Whisper/Groq)
  core/           # Pydantic settings, OS keychain credential store
  tts/            # ElevenLabs TTS
  tools/          # LangChain tools (time, etc.)
  webui/          # Frontend HTML (Live2D + PixiJS)
  Yumi_Avatar/    # Live2D model files (not included — see setup above)
  cli.py          # Typer CLI entry point (yumi command)
```

---

## 🔐 Security

Yumi never stores API keys on disk in plaintext.
All secrets go through the [`credential_store.py`](src/yumi/core/credential_store.py)
module which delegates to your OS's native keychain:

- **Windows** → Windows Credential Manager
- **macOS** → macOS Keychain
- **Linux** → GNOME Keyring / KWallet (via libsecret)

Non-sensitive preferences (personality, provider choice) are saved to `~/.yumi/config.json`.

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
