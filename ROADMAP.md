# 🌸 Yumi Roadmap

Welcome to the Yumi roadmap! This document outlines the planned features, architectural improvements, and community goals for the project. 

If you are a contributor looking for a place to start, this is the perfect guide.

## 🚀 Near-Term Goals (v1.x)

*   **Local TTS Integration (Kokoro):** Implement a fully offline, high-quality Text-to-Speech provider using Kokoro, removing the reliance on cloud APIs (ElevenLabs/CAMB.ai) for users who want 100% privacy.
*   **System Voice Fallback:** Add a basic OS-level TTS provider (e.g., using `pyttsx3` or native macOS/Windows voices) as a reliable offline fallback.
*   **Logging Refactor:** Replace all `print()` statements across the engine and API with a structured Python `logging` setup to allow users to control verbosity and debug issues more effectively.

## 🧠 Mid-Term Goals (Reasoning & Memory)

*   **Long-Term Memory:** Expand LangGraph state to include persistent memory storage (e.g., ChromaDB or local SQLite) so Yumi can remember user preferences and past conversations across sessions.
*   **Multimodal Input (Vision):** Allow Yumi to "see" the screen or use a webcam via multimodal LLMs (like Llama-3.2-Vision or GPT-4o).
*   **Advanced Tool Use:** Add more tools to `src/yumi/tools/` (e.g., weather, web search, local file execution) and enable the reasoning agent to utilize them fluidly.

## 🎨 Frontend & Avatar

*   **WebUI Redesign:** Modernize the `index.html` frontend with React/Next.js for a more responsive and customizable interface.
*   **Custom Avatars:** Build a simple pipeline for users to load their own Live2D models (`.moc3` files) without diving into the code.
*   **Emotion Synchronization:** Improve the mapping between LLM-generated emotional states and Live2D model expression parameters for more lifelike reactions.

## 🤝 Community & Ecosystem

*   **Plugin System:** Create a standard interface for community-built plugins (new personalities, new tools, custom STT models).
*   **Dockerization:** Provide a `Dockerfile` and `docker-compose.yml` for seamless, one-click deployment across all OS environments.

---

*Want to help? Check out [CONTRIBUTING.md](./CONTRIBUTING.md) and grab an issue!*
