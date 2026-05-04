# Yumi Experiments - Model Selection Journey

Hey there! If you're reading this, you're probably curious about how Yumi came to life or maybe you're thinking about tweaking her brain. This folder is basically my messy workshop where I tried a bunch of stuff until something worked.

## What's This All About?

Building Yumi wasn't straightforward. I had to pick the right models for speech recognition, text-to-speech, and the LLM brain - all while trying not to burn through my wallet or make her sound like a robot from the 90s. These experiments are the journey of figuring out what works, what doesn't, and why.

## The Models I Tried

### Speech-to-Text (STT)

| Model | Why I Tried It | Why It Didn't Make the Cut |
|-------|---------------|---------------------------|
| **OpenAI Whisper (local)** | The OG, everyone uses it | Too slow for real-time, eats GPU for breakfast |
| **faster-whisper** | Optimized version, CPU-friendly | **Currently using this!** Good balance of speed/accuracy |
| **Groq Whisper API** | Crazy fast, no local model download | Requires internet, API costs add up, latency varies |
| **HuggingFace API** | Free tier exists | Rate limits, inconsistent uptime |

I landed on `faster-whisper` because I wanted Yumi to work offline and not cost me money every time someone says "hello." The Groq API was genuinely impressive speed-wise, but I don't want to depend on internet connectivity for a personal companion.

### Text-to-Speech (TTS)

| Model | Why I Tried It | Why It Didn't Make the Cut |
|-------|---------------|---------------------------|
| **ElevenLabs** | Best quality hands down | **Currently using this** - pricey but worth it for the voice |
| **Kokoro (local)** | Free, offline, lightweight | Sounds robotic, anime voice doesn't fit Yumi's personality |
| **Groq Orpheus** | Cheap, fast | Voice quality wasn't great, limited emotion control |
| **Typecast Anime** | Made for anime characters | Expensive, API was clunky, latency issues |

Yeah, I picked the expensive one. Sue me. ElevenLabs just sounds *good* and Yumi deserves to sound human. I might revisit local TTS in the future if I find something better than Kokoro.

### LLM / Brain

I experimented with a few providers but settled on **Groq's Llama 3.3 70B**. The key innovation here was using **structured output** (Pydantic schema) to force the LLM to return not just text, but also emotion and motion labels that sync with the Live2D animations.

Other options like local Llama via Ollama were too slow for real-time conversation. OpenAI GPT-4 was great but way too expensive for a project I want to chat with for hours.

**The Problem:** Even with Groq's decent pricing, Yumi burns through tokens like crazy because of the long personality prompt and conversation history. Every single request sends that massive tsundere system prompt plus the chat context. It adds up fast.

**The Plan:** I'm working on **fine-tuning a model** specifically for Yumi's personality. The idea is to bake her character directly into the model weights so I can cut the context length significantly. Instead of sending a novel-length prompt every time, a fine-tuned model would just *know* how to be Yumi. I've kind of started on this already, but it's early days. Will see how it goes.

## About These Notebooks

Fair warning: these experiments are sloppy. They're messy Jupyter notebooks with inconsistent formatting, random code cells, and comments that might not make sense to anyone but me. I cleaned some up with AI help, but honestly, they're still a work in progress.

**The docs are incomplete.** I generated some of the markdown explanations using AI because when I was experimenting, I was just throwing things at the wall to see what sticks. If you want to understand something specific, you might need to actually read the code or run the notebooks yourself.

## Feel Free to Experiment!

Seriously, mess around here. Try a different STT model, swap in a cheaper TTS, test a local LLM. The current setup works, but it's definitely not the only way to build something like Yumi. Some ideas:

- Try `whisper-large-v3` if you have a good GPU
- Test out new local TTS models (there's new stuff every month)
- Swap Groq for Ollama if you want 100% offline operation
- Experiment with different personality prompts in `14_llm_prompt_engineering.ipynb`

## Future Plans

I'll probably clean these notebooks up eventually, make them actually readable, add better documentation. But if you want to fix something now - go for it! Just let me know what you're planning so we don't step on each other's toes.

Keep an eye on this space. More experiments coming as I find new models worth testing.

---

*These experiments represent hours of trial and error. Learn from my mistakes, or make your own. Either way, have fun building!*
