# Yumi: Real-Time AI Companion

A high-performance, real-time AI companion system integrating advanced Speech-to-Text (STT), Large Language Models (LLMs), Text-to-Speech (TTS), and Live2D avatars via WebSockets.

[![Python Version](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-100905?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![WebSocket](https://img.shields.io/badge/WebSocket-Real--Time-green.svg)](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API)
[![Live2D](https://img.shields.io/badge/Live2D-Cubism-pink.svg)](https://www.live2d.com/)

## Overview
Yumi is an interactive, real-time virtual companion architected for ultra-low latency conversational AI. By orchestrating a Python backend with an HTML5/PixiJS frontend, the system captures voice inputs, processes them through a LangChain-powered state machine, and streams audio back synchronously with Live2D lip-sync and emotional expressions.

## Vision
Yumi started as a personal hobby project with a dream of building a genuinely empathetic AI companion. While she is currently a highly responsive conversational agent capable of expressing emotion, the ultimate vision is to evolve her into a proactive companion who can help manage your daily life—checking emails, setting reminders, and seamlessly integrating into this rapidly evolving technological era. 

Read more about the future of this project in [VISION.md](VISION.md).

## Key Engineering Features
- **Real-Time Pipeline**: Connects `faster-whisper` for local voice recognition, LLMs for intent and dialogue generation, and ElevenLabs for voice synthesis.
- **WebSocket Streaming**: Bi-directional event-driven architecture utilizing FastAPI WebSockets to push audio chunks and animation triggers to the frontend.
- **Dynamic Persona Management**: Engineered with optimized prompt templates to simulate 6 unique personalities (Caring, Tsundere, Genki, Kuudere, Yandere, Dandere), adjusting token consumption by ~50%.
- **Live2D Cubism SDK Integration**: Driven by PixiJS on the frontend, rendering fluid body movements, context-aware facial expressions, and real-time lip-syncing mapped to TTS audio data.
- **Pluggable Architecture**: Modular dependency design allowing hot-swapping of LLM providers (Groq, OpenAI, Anthropic) via dependency injection and `pydantic-settings`.

## Tech Stack
- **Backend Core**: Python 3.12+, FastAPI, WebSockets, Uvicorn, LangGraph, LangChain
- **AI Models**: Faster-Whisper (Local STT), ElevenLabs API (TTS), Groq/OpenAI/Anthropic (LLM)
- **Frontend**: HTML5, PixiJS, Live2D Cubism Web SDK
- **Testing & Tooling**: Pytest, Ruff, Mypy, Typer (for CLI)

## Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/yumi.git
   cd yumi
   ```

2. **Set up the virtual environment & install dependencies:**
   Yumi uses standard packaging with `pyproject.toml`.
   ```bash
   pip install -e .
   ```
   *(For development dependencies, run `pip install -e .[dev]`)*

3. **Configure Environment Variables:**
   Create a `.env` file in the project root (or copy `.env.example`):
   ```env
   ELEVENLABS_API_KEY=your_api_key
   LLM_PROVIDER=Groq  # Or OpenAI, Anthropic
   GROQ_API_KEY=your_api_key
   PERSONALITY=caring
   ```

## Live2D Model Setup

Due to licensing and distribution restrictions, the specific Live2D avatar model used by Yumi is not bundled with this repository. 

1. **Acquire the Model**: Navigate to [Booth.pm](https://booth.pm/) and search for your preferred Live2D model (ensure it is compatible with the Live2D Cubism SDK).
2. **Download**: Purchase and/or download the model archive. 
3. **Placement**: Extract the downloaded model files and place them into the designated asset directory:
   ```
   src/yumi/Yumi_Avatar/
   ```
4. **Ready to Go**: Once the files are in the `Yumi_Avatar` directory, the application will automatically load the model on startup.

## Running Yumi

Once the dependencies are installed and the Live2D model is placed:

1. Start the CLI and backend server:
   ```bash
   yumi
   ```
2. The CLI will provide a local URL (typically `http://localhost:8000`).
3. Open this URL in your web browser, allow microphone permissions, and start talking to your companion.

## System Architecture
```text
[ User Voice ] -> (Frontend/WebRTC) -> [ WebSocket ] -> (FastAPI Backend)
                                                             |
                                                       [ VAD / Whisper STT ]
                                                             |
[ Lip-Sync & Emotion Sync ] <- [ ElevenLabs TTS ] <- [ LangChain / LLM Agent ]
             |
      (Live2D Avatar)
```

## Contributing
Contributions, issues, and feature requests are welcome.
See [CONTRIBUTING.md](CONTRIBUTING.md) for more details.

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
