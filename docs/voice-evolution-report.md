# Yumii Voice — Evolution Report & Overhaul Plan

**Scope:** voice latency (slow first word) and barge-in (can't interrupt mid-speech, mid-reply stalls).
**Date:** 2026-09-03 · **Machine benchmarks:** i5-13500H-class CPU, fp32 Kokoro, real runtime config.
**Runtime config used for analysis** (`~/.yumii/config.json`): Groq STT · Ollama `minimax-m3` · Kokoro fp32 (`af_heart`).

---

## TL;DR

Yumii's voice latency was already attacked once — commit `8bcea55` ("pacing-aware chunking,
voice starts ~3s sooner") is a hand-built first-chunk-first speed hack. It worked (3.8 s → 1.5 s
to first word **at the TTS stage**) but it carries a built-in flaw: its pacing budget assumes
Kokoro RTF < 0.71, while today's measurement on this machine is **RTF 0.72–0.85**. The margin
went negative → **the mid-sentence pauses are that hack coming home to roost**. The commit itself
recorded a "worst mid-reply stall 0.38 s" — the failure mode was visible on day one.

The remaining latency is structural: nothing reaches TTS until the **entire LLM reply is done**.
The fix plan (4 phases) takes first word from ~3.5–6 s to **~1–2 s**, eliminates stalls via a
prefetch pipeline, and enables real barge-in.

---

## 1. The pipeline as it stands

```
webui mic (16 kHz, AEC on) → WS → audio_input_queue
  → Silero VAD (engine.py:534 / stt.py)  [speech start → interrupt, but suppressed while is_speaking]
  → VAD end-of-turn: 12 silent frames ≈ 384 ms tail (stt.py:22-24)
  → Groq Whisper transcribe (runs only AFTER the tail) → transcription_queue
  → LangGraph astream (engine.py:626)  [tokens streamed to UI only]
  → FULL reply ready → tts_queue (engine.py:783)
  → Kokoro chunker (kokoro_speaker.py:52) → synth chunk-by-chunk → WS → browser playback
```

Every stage waits for the previous one to *fully* finish. That is the disease; the phases below
are the cure, in impact order.

## 2. Evolution so far — the speed hacks already shipped

| Commit | What it did | Result |
|---|---|---|
| `1ab5fb1` (v0.9) | Kokoro-82M local TTS | Whole reply synthesized as one block → ~3.8 s silence between text and voice |
| **`8bcea55`** (Jul 7) | **The forgotten change**: pacing-aware chunker — 48-char first chunk, later chunks ≤ 1.4× audio already delivered, 80 ms gap between chunks, ONNX warmup at boot | Text-visible → voice: **3.8 s → 1.5 s**. But pacing assumes RTF < 0.71; measured "worst mid-reply stall 0.38 s" already noted in the commit |
| `0093e62` (Jul 16) | Speak narration/fillers during tool calls ("Let me check that for you") | No dead air during tools — works, keep it |

**Verdict on `8bcea55`:** it did its job and is worth keeping in spirit — but (a) its 1.4×
budget math is the direct cause of today's mid-speech stalls, and (b) it only accelerates the
TTS stage; the wait-for-full-LLM-reply latency above it was never addressed.

## 3. Measured on this machine (2026-09-03)

| Measurement | Value | Implication |
|---|---|---|
| Kokoro fp32, first 48-char chunk | **2.19 s** synth | First word is gated on this *after* the LLM finishes |
| Kokoro fp32, steady-state RTF | **0.72–0.85** | Needs < 0.71 for the current budget math → stalls guaranteed on longer replies |
| Kokoro int8 | ~3.7× slower on x86 (own note in `kokoro_model.py`) | **Do not switch** — fix pacing structurally instead |
| faster-whisper base, 3–6 s audio (local) | 3.2–3.3 s | Currently unused (Groq STT is active) — only relevant if going offline again |
| Groq STT round-trip | ~0.3–1.0 s (typical) | Fine; starts only after the 384 ms VAD tail |

## 4. Root causes

- **R1 — Whole reply before TTS.** `reasoning_engine_task` queues only the final result
  (`engine.py:783`, assembled at `on_chain_end`, `engine.py:657-684`). Tokens already stream to
  the UI (`thinking_delta`) — the plumbing exists, TTS just isn't on it. *This is ~70% of perceived latency.*
- **R2 — TTS pacing margin violated.** `kokoro_speaker.py:32-34`: budget growth 1.4× requires
  RTF < 0.71; measured 0.72–0.85. Playback catches up, buffer drains, she pauses. Plus a baked-in
  80 ms gap per chunk (`_CHUNK_GAP_SEC`) — an audible hiccup even when healthy.
- **R3 — Dumb end-of-turn.** Fixed `SILENCE_END_FRAMES = 12` ≈ 384 ms dead tail on every turn
  (`stt.py:22-24`); also cuts the user off when they pause mid-thought.
- **R4 — Barge-in disabled by design.** `on_speech_start` returns early while `is_speaking`
  (`engine.py:537-544`). She cannot be interrupted mid-speech, period. (Guard was for mic/speaker
  feedback; the webui already plays with `echoCancellation: true` in the same AudioContext, which
  is the setup Pipecat/LiveKit rely on for exactly this.)
- **R5 — Two echo bugs hiding behind R4's guard:**
  1. `is_speaking = False` the moment the last chunk is *sent* (`engine.py:866`), while the
     browser plays queued audio for seconds more → VAD goes live on the playback tail → spurious self-interrupt.
  2. Capture state is never reset after her turn: while she speaks, mic audio (hers, through
     imperfect AEC) can trip the internal `triggered` flag in `stream_capture` and accumulate as a
     "user utterance" — her own leaked voice can come back as a phantom user message.

## 5. Fix plan (each phase is independently shippable + testable)

### Phase 1 — Token→sentence→TTS streaming (kills R1)
- Feed `on_chat_model_stream` tokens through the existing `_split_speech_chunks` logic
  incrementally; queue each completed sentence to TTS as soon as it closes. First word lands
  after the **first sentence**, not the whole reply.
- Files: `core/engine.py` (reasoning loop), `tts/kokoro_speaker.py` (accept an async text stream).
- Reference: Pipecat's LLM→TTS sentence aggregation (`pipecat-ai/pipecat`,
  `src/pipecat/processors/` aggregators; MIT).
- Watch out: think-block stripping (`_THINK_BLOCK`) and expression/motion synthesis must run on
  the finalized sentence, not the raw token; tool-pass narration flow stays as is.
- Expected: first word ~3.5–6 s → **~1–2 s** (bounded by Groq TTFT + first-chunk synth).

### Phase 2 — TTS prefetch + pacing v2 (kills R2)
- Decouple synthesis from yielding: a synthesis worker pushes finished chunks into a queue ≥ 1–2
  chunks ahead (jitter buffer). Requirement drops from "RTF < 0.71 with zero gap" to
  "average RTF < 1.0" — measured 0.72–0.85 fits.
- Make chunk sizing time-aware (measure actual synth duration, adapt budget) instead of a fixed
  1.4× character guess; drop the 80 ms gap (use ~20 ms crossfade/trim or nothing — chunks already
  end at clause boundaries).
- Files: `tts/kokoro_speaker.py`, `core/engine.py` (tts_speaker_task consumption stays identical).
- Expected: **zero mid-reply stalls**; first chunk slightly smaller (~24–32 chars) → first word sooner.
- Test: long replies (300+ chars) with Ollama + memory review running concurrently; assert no
  `nextPlayTime < currentTime` underruns in the webui.

### Phase 3 — Real barge-in + echo hygiene (kills R4, R5)
- Remove the blanket `is_speaking` veto. During playback require a **stricter trigger**:
  ~300–400 ms of continuous high-confidence Silero speech (LiveKit's `interruption.min_duration`
  idea; `docs.livekit.io/agents/logic/turns/tuning/`).
- On interrupt: broadcast stop → webui `stopAllAudio()` (exists) → cancel in-flight
  `stream_speak` generator → drain `tts_queue` **immediately** (today it's only drained at the
  *next* turn, `engine.py:588-592`) → deny any pending HITL confirmation (hook already does this).
- Add a `playback_finished` WS message from the webui; only then set `is_speaking = False`.
- Reset VAD/triggered/STT state whenever her turn ends, so leaked playback audio can never
  become a phantom user utterance (R5.2).
- Files: `core/engine.py`, `assets/webui/index.html`, `audio/stt.py`.
- Test: with speakers (not headphones), talk over her mid-sentence → she stops ≤ ~0.5 s and
  answers the interruption; no phantom turns after she finishes.

### Phase 4 — Smart end-of-turn (kills R3)
- Cut `SILENCE_END_FRAMES` to ~6 (~190 ms) and gate the turn decision on **Smart Turn v3**
  (`pipecat-ai/smart-turn`, BSD-2-Clause, 8 MB int8 ONNX, ~65 ms on CPU, 16 kHz PCM, offline):
  VAD silence → feed the utterance → "done" vs "still mid-thought".
- Optional stretch (LiveKit-style **preemptive generation**): start the LLM on Groq STT's final
  text immediately; abort and regenerate if Smart Turn says the user wasn't done.
- Files: `audio/stt.py`, `core/models.py` (add model download), `pyproject.toml` (onnxruntime already present).
- Test: pause mid-sentence for 1 s → she waits; finish a short command → response starts fast.

## 6. Latency budget — before / after

| Stage | Today | After phases 1–4 |
|---|---|---|
| VAD end-of-turn tail | ~384 ms fixed | ~190 ms + smart-turn (~65 ms) |
| STT (Groq) | 0.3–1.0 s, serial | same, but overlappable (preemptive start) |
| LLM | **full completion** before TTS | first sentence only (~0.3–0.8 s TTFT on Groq; Ollama: TTFT-bound) |
| TTS first chunk | ~2.2 s (48 chars, fp32) | ~0.8–1.2 s (smaller chunk, warm session) |
| Mid-reply stalls | guaranteed on long replies | none (prefetch) |
| **First word** | **~3.5–6 s** | **~1–2 s** |
| Barge-in | impossible mid-speech | yes, ~0.3–0.5 s to stop |

## 7. Non-goals and traps

- **int8 Kokoro on x86** — measured ~3.7× slower (fallback kernels); noted in `kokoro_model.py`. Don't.
- **Moshi / HF speech-to-speech** — GPU-bound, no tools/memory/personality; would abandon the LangGraph brain. Revisit only for a future realtime "voice skin".
- **LiveKit runtime** — best-in-class UX but wants its SFU + rooms; borrow ideas (preemptive generation, interruption gating), not the stack.
- **WebView2 caveat** — Chromium honors `echoCancellation`, but AEC quality on external speakers is the one thing to verify empirically (Phase 3's strict gate is the fallback if echo leaks).

## 8. Acceptance criteria

- [ ] Ask a question that deserves a 3-sentence answer → first word ≤ ~1.5 s after you stop talking.
- [ ] A 300+ char reply plays with zero audible stalls (concurrent Ollama load included).
- [ ] Speaking over her mid-sentence stops her within ~0.5 s, and she addresses the interruption.
- [ ] Pausing 1 s mid-thought does not trigger a response.
- [ ] No phantom turns / self-transcriptions after she finishes speaking.
- [ ] Regression: tool-call narration still speaks during tools; HITL barge-in still denies.
