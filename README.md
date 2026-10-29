<div align="center">

<img src="docs/public/mascot.png" alt="Yumii" width="280">

# Yumii

**the AI companion that's actually yours.**

she talks out loud, listens in real time, does things for you —
and remembers your life together. her memory lives on your machine;
her mind is **NVIDIA Nemotron on Nebius Token Factory** — or a local
model, if you'd rather nothing leave it at all.

[![Version](https://img.shields.io/badge/version-0.15.0-orange.svg)](CHANGELOG.md)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://python.org)
[![Mind: NVIDIA Nemotron](https://img.shields.io/badge/mind-NVIDIA%20Nemotron-76B900.svg)](#built-with-nvidia-nemotron-on-nebius-token-factory)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/CodeNeuron58/Yumii?style=social)](https://github.com/CodeNeuron58/Yumii)

<video src="https://github.com/user-attachments/assets/f7a2a3c7-651d-4b08-ab42-e7e7adb0f48e" width="100%" controls></video>

**Experimental preview.** Windows-first; expect rough edges.

</div>

---

## Who she's for

People who spend long hours alone at their computer — students, remote
workers, solo builders — who want an always-on companion they can simply
talk to: one that remembers their life and helps with everyday tasks,
without their private memories living on someone else's server.

## Install

**Windows** (PowerShell):

```powershell
iex (irm https://yumii.me/install.ps1)
```

A short setup asks you to pick her mind, ears and voice — the
recommended mind is **NVIDIA Nemotron on Nebius Token Factory**, which
needs one API key from
[tokenfactory.nebius.com](https://tokenfactory.nebius.com/project/api-keys).
She lands in your Start Menu, downloads her voice the first time you open
her, and then you just talk.

**Updating:** re-run the same command.

### Run from source (developers)

```powershell
git clone https://github.com/CodeNeuron58/Yumii && cd Yumii
uv sync --extra dev                      # Python backend (needs uv)
cd desktop && npx @tauri-apps/cli dev     # the desktop app (needs Rust + Node)
```

Paste your Nebius Token Factory key in the first-run card (or the
dashboard). Optional: a [Tavily](https://app.tavily.com) key in the
dashboard gives her Tavily-powered web search.

## Uninstall

```powershell
uv tool uninstall yumii                       # the backend
Remove-Item "$env:LOCALAPPDATA\Yumii" -Recurse   # the app
Remove-Item "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Yumii.lnk"
```

Delete `~/.yumii` too and she forgets everything — keep it and she's
portable.

---

## What she does

- **talks in real time** — streamed speech, barge-in, and end-of-turn
  detection that knows a pause from a finished thought
- **does things** — web search (Tavily), Gmail, Calendar, Notion — every
  action that sends or changes something sits behind a permission gate
- **remembers** — searches every past conversation, saves and corrects
  her own facts about you, knows when you last talked and what was
  going on
- **stays herself** — six personalities, each a text file you can edit,
  tuned against a scripted conversation suite (short spoken replies,
  honest pushback instead of flattery, no guilt-trip goodbyes)

## Built with NVIDIA Nemotron on Nebius Token Factory

- **Nemotron 3 Super** is her mind: every conversation turn and every tool
  call (web search, memory, email). First word in about a second.
- **Nemotron 3 Nano** does her background thinking — reviewing what to
  remember and summarizing past conversations — at a fifth of Super's
  price, through the same Token Factory key.
- **Reasoning switched off on the voice path** (`enable_thinking: false`).
  Measured on Token Factory: a reasoning pass put Nano's first word at
  8.4 s instead of 0.8 s, and Nemotron 3.5 Lightning spoke its own
  "thinking process" aloud — unacceptable for a voice companion.
- **Cold-start warm-up:** a cold serverless endpoint took 12.6 s to the
  first token (vs ~1 s warm), so Yumii sends a one-token warm-up while she
  boots and when you start speaking after a quiet spell.
- **Live model list:** the dashboard lists the tool-capable models your
  Token Factory key can use (Nemotron Super, Nano, 3.5 Lightning, 3.5
  Super VL, Ultra), straight from the `/v1/models` endpoint.
- **NVIDIA Nemotron Speech** (streaming speech recognition) is also
  selectable as an experimental on-device ear, via sherpa-onnx.

Token Factory's OpenAI-compatible API is why adding it took one wiring
entry: Yumii's model catalog is data-driven, so Nebius plugged into the
existing tool-calling agent without new code paths.

## Mix and match

| Role | Options |
|------|---------|
| **Mind** | **NVIDIA Nemotron via Nebius Token Factory** *(default)* · Groq · Gemini · OpenRouter · DeepSeek · xAI · Together · Mistral · OpenCode · Ollama *(local or cloud)* · OpenAI · Anthropic |
| **Ears** | Local Whisper *(offline)* · Groq Whisper *(fast)* · Vosk *(offline streaming)* · NVIDIA Nemotron Speech · Moonshine *(both experimental)* |
| **Voice** | **Kokoro** *(local, free)* · ElevenLabs · CAMB.ai |
| **Web search** | **Tavily** *(with a key)* · DuckDuckGo *(free fallback)* |

Everything switches from the in-app dashboard.

---

<div align="center">

**Private by architecture** — no account, no telemetry, no server of ours.
Your memories stay on your machine; conversation text goes only to the
model provider you choose — or nowhere at all, with a local model.

</div>

---

## Roadmap

- **Proactiveness, done properly** — reminders you ask for first, gentle
  offers instead of guesses, and silence as the default; researched and
  designed, not yet built
- **Seeing your screen** — she looks at what you're looking at and helps
- macOS & Linux shells · more voices and languages

## Contributing

The easiest contribution in open source: **a personality is one text
file** in [`src/yumii/assets/prompts/`](src/yumii/assets/prompts/) —
copy one, rewrite the character, open a PR. Adding a speech or voice
provider is one self-registering module in `src/yumii/audio/providers/`
or `src/yumii/tts/providers/` — see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE). She's yours.
