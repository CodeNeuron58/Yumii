<div align="center">

<img src="docs/public/mascot.png" alt="Yumii" width="280">

# Yumii

**the AI companion that's actually yours.**

she talks out loud, listens in real time, does things for you —
and remembers your life together. all on your machine:
no account, no cloud, nothing ever leaves it.

[![Version](https://img.shields.io/badge/version-0.14.0-orange.svg)](CHANGELOG.md)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://python.org)
[![Runs on CPU](https://img.shields.io/badge/runs%20on-CPU-informational.svg)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/CodeNeuron58/Yumii?style=social)](https://github.com/CodeNeuron58/Yumii)

<video src="https://github.com/user-attachments/assets/f7a2a3c7-651d-4b08-ab42-e7e7adb0f48e" width="100%" controls></video>

**Experimental preview.** Windows-first; expect rough edges.

</div>

---

## Install

**Windows** (PowerShell):

```powershell
iex (irm https://yumii.me/install.ps1)
```

That's it. She lands in your Start Menu, downloads her voice and ears
the first time you open her, asks for **one API key** (a free
[Groq](https://console.groq.com) key is the easiest start), and then
you just talk.

**Updating:** re-run the same command.

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

- **talks in real time** — speak, interrupt, talk over her, like a real
  conversation; barge-in works
- **does things** — web search, Gmail, Calendar, Notion — every action
  behind a permission gate you control
- **remembers** — searches every past conversation, writes and corrects
  her own facts about you, knows what happened last time
- **stays local** — her voice and ears run on your CPU; pick cloud or
  fully-offline, your keys never leave the machine

## Pick a vibe

Six personalities out of the box — **Caring**, **Tsundere**, **Genki**,
**Kuudere**, **Dandere**, **Yandere** — and each one is a single text
file you can edit or write from scratch.

## Mix and match

| Role | Options |
|------|---------|
| **Mind** | Groq *(free tier)* · Gemini · OpenRouter · DeepSeek · xAI · Together · Mistral · OpenCode · **Ollama** · OpenAI · Anthropic |
| **Ears** | Local Whisper *(offline)* · Groq *(fast)* · Vosk *(offline streaming)* |
| **Voice** | **Kokoro** *(local, free)* · ElevenLabs · CAMB.ai |

Everything switches live from the in-app dashboard. Go fully offline
and nothing ever leaves the machine.

---

<div align="center">

**Private by architecture** — no account, no telemetry, no server of ours.
Your data goes only to the providers you choose, or nowhere at all.

</div>

---

## Roadmap

- **Seeing your screen** — she looks at what you're looking at and helps
- **Proactiveness** — she speaks first when it matters
- macOS & Linux shells · more voices and languages

## Contributing

The easiest contribution in open source: **a personality is one text
file** in [`src/yumii/assets/prompts/`](src/yumii/assets/prompts/) —
copy one, rewrite the character, open a PR. Bigger leaps welcome:
new TTS/STT backends, tools, shells — see
[CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE). She's yours.
