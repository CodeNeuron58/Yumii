# Yumii Voice Speed — Implementation Checklist

Companion to `docs/voice-evolution-report.md`. Phases 1–4 from that report
(streaming, prefetch, barge-in, Smart Turn) are **done** on `feat/voice-realtime`.
This is the next tier: how to go from ~1–2 s first-word latency to the
cascade-industry ~0.5–1 s class. Ordered by impact; each item is independent.

**The one rule:** total latency is the sum of the *tails* between stages. Shrink
tails and overlap stages — never optimize a stage that isn't on the critical path.

---

## P0 — Measure first (do this before anything else)

- [ ] **Per-turn latency instrumentation.** Log one event per turn with the
      timestamps that matter: `user_stopped → smart_turn_verdict → stt_final →
      llm_first_token → first_audio_chunk_sent → playback_finished`. One
      structured log line (e.g. `turn_latency` with deltas) plus a rolling
      p50/p95 in the dashboard status.
      *Files:* `core/engine.py`, `audio/stt.py`, `webui/index.html` (echo back
      actual playback start). ~1–2 h.
- [ ] **Record a baseline table** with the current branch before touching
      anything (idle machine + Ollama loaded + Discord-style background load).
      Without this you're tuning blind.

## P1 — Eager generation (the big one; the "feels telepathic" trick)

The LLM currently waits for Groq's *final* transcript. Cascade leaders start
the LLM on *unconfirmed* text and cancel if it changes.

- [ ] **Start the LLM on vosk partials.** `VOSK_MODEL_SIZE=medium` is already
      configured. When the partial transcript stabilizes for ~250 ms AND Silero
      reports silence (the Smart Turn trigger point), launch the LLM on the
      partial text. When the Groq final arrives:
      - identical (or edit-distance-close) → keep the run, discard nothing;
      - different → cancel the stream, re-run on the final text
        (LiveKit `preemptive_generation` semantics: `max_retries=3`,
        skip for utterances > 10 s).
      *Files:* `core/engine.py` (new speculative branch in the reasoning task),
      `audio/stt.py` (expose stabilized partials as an event).
- [ ] **Reconcile, don't restart, when cheap.** If only the tail differs
      (e.g. partial "book me a table" → final "book me a table for two"),
      keep the already-streamed sentences and only regenerate from the delta.
      Start naive (restart), upgrade only if measurements show wasted restarts.
- [ ] **Race Smart Turn against STT upload.** At the silence trigger, start
      the Groq upload *and* Smart Turn inference concurrently; if Smart Turn
      says "incomplete", abort the upload. Upload of a 5 s WAV is ~0.1–0.3 s —
      hiding it inside the 190 ms listen window is free latency.
      *Files:* `audio/stt.py`, `audio/stt_providers.py`.
- [ ] **Optional: Groq streaming transcription** instead of batch-per-utterance
      if/when the API supports it — final-pass latency drops to ~a token-time.

## P2 — First-word micro-latency (each shaves 100–400 ms)

- [ ] **Smaller first TTS chunk.** `_FIRST_CHUNK_BUDGET` 32 → 20 chars
      (~0.6–0.8 s first audio vs measured 1.18 s). Verify words don't feel
      clipped; the chunk gap change (40 ms) may need retuning with shorter chunks.
      *File:* `tts/kokoro_speaker.py`.
- [ ] **Greeting/opening cache.** Kokoro synthesis of a canned opener ("Sure!",
      "Okay", "Mm—") pre-rendered at boot; if the first streamed sentence starts
      with one, splice the cached audio (~0 ms TTFA) and synthesize the rest.
      Cheap 80% case, purely additive. *File:* `tts/kokoro_speaker.py`.
- [ ] **Tune Smart Turn's ask delay.** `SILENCE_END_FRAMES_QUICK` 6 → 4 frames
      (~130 ms). Re-run the false-interruption test suite (pause mid-thought)
      before shipping. *File:* `audio/stt.py`.
- [ ] **STT provider budget:** measure Groq round-trip under your network; if
      >400 ms, try `whisper-large-v3-turbo` vs whatever's configured, or vosk
      medium as the *final* transcript for short commands (0 ms network).
- [ ] **Binary WebSocket audio frames.** Replace base64-JSON `audio_chunk` with
      raw PCM16 binary WS messages (header + payload). ~33% less wire, no
      base64 encode/decode per chunk. Keep JSON for control messages.
      *Files:* `api/server.py`, `webui/index.html`, `core/engine.py`.

## P3 — LLM time-to-first-token (provider-side, biggest single variance)

- [ ] **Ollama keep-alive.** `OLLAMA_KEEP_ALIVE=-1` (or config field) so
      `minimax-m3` never unloads between turns — a cold model load is seconds.
- [ ] **Measure TTFT per provider** and consider a routing rule: short
      conversational turns → Groq; long/tool-heavy turns → Ollama. Even a
      simple `len(user_text) < N` heuristic works.
- [ ] **Prompt-prefix stability audit.** `session_context` changes per session
      switch only (good), but verify nothing per-turn mutates the prefix —
      any mutation voids provider KV/prefix caches (the date already lives at
      the prompt tail; keep it that way).
- [ ] **History window for TTFT:** `_GROQ_HISTORY_WINDOW = 12` is already lean;
      verify Ollama uses the same budget (`_HISTORY_WINDOW = 40` may be fat for
      a local model's prefill).

## P4 — Hardware / optional

- [ ] **GPU offload for Kokoro.** If a machine has CUDA, run the Kokoro ONNX
      session on `CUDAExecutionProvider` (fp32 GPU model) — RTF drops from
      ~0.8 to ~0.05, making stalls physically impossible. Add a provider
      fallback chain in `tts/kokoro_speaker.py`.
- [ ] **DirectSound/WASAPI exclusive check:** measure the browser
      `audioContext.outputLatency` on target machines; >100 ms is audible and
      argues for smaller jitter buffers in `index.html`.

## Done already (Phase 1–4, `feat/voice-realtime`) — for context

- ✅ Token→sentence→TTS streaming (first word = first sentence)
- ✅ Prefetch synthesis worker (stalls need avg RTF > 1.0; measured 0.72–0.85)
- ✅ Real barge-in (480 ms gated) + playback_finished handshake + capture reset
- ✅ Smart Turn v3 end-of-turn (~190 ms ask, replaces fixed 384 ms tail)

## Verification checklist (run after each item above)

- [ ] First word ≤ ~1 s after user stops (idle machine)
- [ ] First word ≤ ~1.5 s with Ollama loaded + background apps running
- [ ] Pause mid-thought 1 s → no response (false-interrupt regression)
- [ ] Short command ("stop") → response fast AND complete (eager-generation
      reconciliation didn't lose the tail)
- [ ] 300+ char reply → zero underruns (debug `kokoro_chunk` rtf log)
- [ ] Barge-in → she stops ≤ ~0.5 s; no phantom turns after
