# Yumi - AI Waifu 🌸

## Overview
Yumi is an interactive, real-time AI waifu designed to act as your virtual companion. With dynamic, expressive visuals and an intelligent conversational backend, Yumi provides a highly engaging and responsive experience.

## Key Features
- **Interactive AI Companion:** Talk to Yumi directly, and she will respond intelligently with context-aware emotion.
- **Multiple Personality Modes:** Choose from 6 unique personalities - caring (default), tsundere, genki, kuudere, yandere, or dandere. Switch anytime via CLI or voice command!
- **Optimized Prompts:** Efficient personality templates reduce token usage by ~50% for faster, more cost-effective interactions.
- **Real-time Voice Recognition:** Captures and processes your voice seamlessly using Whisper for accurate Speech-to-Text.
- **Lifelike Voice Synthesis:** Utilizes ElevenLabs TTS for incredibly realistic, high-quality, and expressive voice generation.
- **Dynamic Live2D Visuals:** Brought to life using PixiJS and the Live2D Cubism SDK, Yumi reacts to your conversations with fluid body movements.
- **Contextual Facial Expressions:** Yumi's facial expressions dynamically change based on the emotional context of the dialogue, driven by advanced LLM prompts.
- **Expressive Lip Syncing:** Yumi's mouth movements perfectly synchronize with the generated voice in real-time.
- **Seamless Communication:** A robust Python backend powered by FastAPI and WebSockets ensures instant, real-time, low-latency interaction.

## Technologies Bringing Her to Life
- **Intelligence & Voice:** Python, FastAPI, WebSockets, Whisper (Speech-to-Text), ElevenLabs (Text-to-Speech), LLM Integration
- **Visuals & Animation:** HTML5, CSS3, JavaScript, PixiJS, Live2D Cubism SDK

## How to Meet Yumi
1. Clone the repository.
2. Install the necessary Python dependencies: `pip install -r requirements.txt`.
3. Set up your API keys (e.g., ElevenLabs, LLM provider) in your environment configuration.
4. Run `yumi` to launch the CLI dashboard.
5. Configure your senses (API keys) if it's your first time.
6. Optionally, change Yumi's personality from the dashboard or during conversation.
7. Start the interaction and open your browser - allow microphone access and say hello!

## Personalities
Yumi can express herself in 6 different personality modes:

- **Caring** (default): Warm, empathetic, and supportive - a gentle companion who genuinely cares
- **Tsundere**: Playful teasing with a soft heart - acts tough but cares deeply underneath
- **Genki**: Energetic and cheerful - bursting with enthusiasm and optimism
- **Kuudere**: Cool, calm, and rational - shows caring through precise, analytical actions
- **Yandere**: Intensely devoted - sweet but with overwhelming protective affection
- **Dandere**: Shy and introverted - quiet and hesitant, but opens up gradually

**Switching Personalities:**
- Via CLI: Select "💕 Change Personality" from the dashboard
- Via Voice: Say "switch to [personality]", "be [personality]", "become [personality]", or just the personality name

---
*Version 1.2 - Multi-Personality System with Optimized Prompts*
