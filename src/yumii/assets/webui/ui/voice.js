// The live link to her: one WebSocket carrying mic audio out (16 kHz PCM16)
// and events + her voice (PCM16 chunks) back. Knows nothing about the view —
// it reports through the handlers it's given.

import { backend, sleep } from './backend.js';

export class VoiceLink {
    /**
     * handlers: onOpen(), onClose(), onEvent(data), onMicLevel(rms),
     * onMicError(err), onSpeechEnd(seq)
     */
    constructor(handlers) {
        this.h = handlers;
        this.socket = null;
        this.muted = false;
        this.negotiated = false;      // first connect may deep-link ?session=

        this.ctx = null;              // playback
        this.analyser = null;
        this.sources = [];
        this.nextPlayTime = 0;
        this.streaming = false;
        this.sampleRate = 24000;
        this.seq = 0;                 // speech session echoed back on playback_finished
        this.endTimer = null;
        this.byteRemainder = new Uint8Array(0);

        this.micStream = null;        // capture
        this.micContext = null;
        this.micProcessor = null;
    }

    get open() {
        return this.socket?.readyState === WebSocket.OPEN;
    }

    /** Open the audio context and connect; the mic starts once the session is negotiated. */
    start() {
        if (this.ctx) return;
        this.ctx = new (window.AudioContext || window.webkitAudioContext)();
        this.analyser = this.ctx.createAnalyser();
        this.analyser.fftSize = 512;
        this.analyser.connect(this.ctx.destination);
        // WebView2 may start audio contexts suspended (autoplay policy).
        const resume = () => {
            for (const c of [this.ctx, this.micContext]) {
                if (c && c.state === 'suspended') c.resume().catch(() => {});
            }
        };
        window.addEventListener('pointerdown', resume);
        window.addEventListener('keydown', resume);
        document.addEventListener('visibilitychange', resume);
        this.connect();
    }

    connect() {
        const socket = new WebSocket(backend.wsUrl);
        socket.binaryType = 'arraybuffer';
        this.socket = socket;

        socket.onopen = () => {
            // The session is negotiated before any audio flows: the first
            // connect honours a ?session= deep link, reconnects keep the
            // active session ("auto") instead of minting a new one.
            const resumeId = !this.negotiated && new URLSearchParams(location.search).get('session');
            socket.send(JSON.stringify(resumeId
                ? { type: 'session_select', action: 'resume', session_id: resumeId }
                : { type: 'session_select', action: 'auto' }));
            this.negotiated = true;
            // The backend's mute flag doesn't survive its own restarts.
            if (this.muted) this.send({ type: 'mic_mute', muted: true });
            if (!this.micStream) this.initMic();
            this.h.onOpen?.();
        };
        socket.onmessage = (event) => {
            if (typeof event.data !== 'string') return;
            let data;
            try { data = JSON.parse(event.data); } catch { return; }
            this.dispatch(data);
        };
        socket.onclose = () => {
            if (this.socket !== socket) return;
            this.stopAudio();
            this.h.onClose?.();
            setTimeout(() => this.connect(), 3000);
        };
    }

    send(payload) {
        if (!this.open) return false;
        this.socket.send(JSON.stringify(payload));
        return true;
    }

    command(text) { return this.send({ type: 'command', command: text }); }
    speak(text) { return this.send({ type: 'speak', text }); }
    answer(requestId, approve) {
        return this.send({ type: 'confirmation_response', request_id: requestId, approve });
    }

    /** Mute is a gate, not a teardown: the stream stays attached so unmute is instant. */
    setMuted(muted, { tell = true } = {}) {
        this.muted = muted;
        if (this.micStream) this.micStream.getAudioTracks().forEach((t) => { t.enabled = !muted; });
        if (tell) this.send({ type: 'mic_mute', muted });
    }

    // ── Incoming ────────────────────────────────────────────────────────

    dispatch(data) {
        switch (data.type) {
            case 'audio_chunk': this.playChunk(data.data); return;   // hot path
            case 'audio_end': this.finishStream(); return;
            case 'audio_start': this.beginStream(data); break;
            case 'interrupt':
            case 'error': this.stopAudio(); break;
            default: break;
        }
        this.h.onEvent?.(data);
    }

    beginStream(data) {
        this.stopAudio();
        this.streaming = true;
        this.sampleRate = data.sampleRate || 24000;
        this.seq = data.seq || 0;
        this.nextPlayTime = this.ctx.currentTime + 0.1;
    }

    playChunk(base64) {
        if (!this.streaming || !this.ctx) return;
        const samples = this.decode(base64);
        if (!samples.length) return;
        const buffer = this.ctx.createBuffer(1, samples.length, this.sampleRate);
        buffer.getChannelData(0).set(samples);
        const src = this.ctx.createBufferSource();
        src.buffer = buffer;
        const gain = this.ctx.createGain();
        gain.gain.value = 0.7;   // less bleed into the mic
        src.connect(gain);
        gain.connect(this.analyser);
        if (this.nextPlayTime < this.ctx.currentTime) this.nextPlayTime = this.ctx.currentTime + 0.05;
        src.start(this.nextPlayTime);
        this.sources.push(src);
        this.nextPlayTime += buffer.duration;
        src.onended = () => {
            const i = this.sources.indexOf(src);
            if (i > -1) this.sources.splice(i, 1);
        };
    }

    finishStream() {
        if (!this.ctx) return;
        const remaining = Math.max(0, this.nextPlayTime - this.ctx.currentTime);
        const seq = this.seq;
        clearTimeout(this.endTimer);
        this.endTimer = setTimeout(() => {
            this.endTimer = null;
            // A stale timer (an interleaved narration's audio_end, or a
            // superseded session) must not end the live one.
            if (!this.streaming || this.seq !== seq) return;
            // The backend keeps the barge-in gate armed until playback has
            // ACTUALLY finished — the mic can still hear the tail.
            this.send({ type: 'playback_finished', seq });
            this.streaming = false;
            this.h.onSpeechEnd?.(seq);
        }, remaining * 1000 + 400);
    }

    stopAudio() {
        clearTimeout(this.endTimer);
        this.endTimer = null;
        for (const src of this.sources) { try { src.stop(); } catch { /* already stopped */ } }
        this.sources = [];
        this.streaming = false;
        this.nextPlayTime = 0;
        // An odd byte left by a cut-off chunk would turn the next reply to static.
        this.byteRemainder = new Uint8Array(0);
    }

    /** Base64 PCM16 → Float32, carrying an odd trailing byte to the next chunk. */
    decode(base64) {
        const binary = atob(base64);
        const bytes = new Uint8Array(this.byteRemainder.length + binary.length);
        bytes.set(this.byteRemainder);
        for (let i = 0; i < binary.length; i++) bytes[this.byteRemainder.length + i] = binary.charCodeAt(i);
        const whole = Math.floor(bytes.length / 2);
        this.byteRemainder = bytes.slice(whole * 2);
        const pcm = new Int16Array(bytes.buffer, 0, whole);
        const out = new Float32Array(whole);
        for (let i = 0; i < whole; i++) out[i] = pcm[i] / 32768;
        return out;
    }

    // ── Microphone ──────────────────────────────────────────────────────

    async initMic() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                // Echo cancellation is what makes barge-in work on speakers.
                audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
            });
            this.micStream = stream;
            if (this.muted) stream.getAudioTracks().forEach((t) => { t.enabled = false; });

            const ctx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
            this.micContext = ctx;
            const source = ctx.createMediaStreamSource(stream);
            const processor = ctx.createScriptProcessor(4096, 1, 1);
            processor.onaudioprocess = (e) => {
                if (this.muted || !this.open) return;
                const input = e.inputBuffer.getChannelData(0);
                let sum = 0;
                for (let i = 0; i < input.length; i++) sum += input[i] * input[i];
                this.h.onMicLevel?.(Math.sqrt(sum / input.length));
                const pcm = new Int16Array(input.length);
                for (let i = 0; i < input.length; i++) {
                    const s = Math.max(-1, Math.min(1, input[i]));
                    pcm[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
                }
                this.socket.send(pcm.buffer);
            };
            source.connect(processor);
            processor.connect(ctx.destination);
            this.micProcessor = processor;
            // Unplugged headset, sleep/resume: the track ends — get a new one.
            stream.getAudioTracks().forEach((t) => t.addEventListener('ended', () => this.reacquireMic()));
        } catch (err) {
            this.h.onMicError?.(err);
        }
    }

    async reacquireMic() {
        try { this.micProcessor?.disconnect(); } catch { /* gone */ }
        this.micStream?.getTracks().forEach((t) => t.stop());
        this.micContext?.close().catch(() => {});
        this.micStream = null;
        this.micContext = null;
        this.micProcessor = null;
        await sleep(500);
        this.initMic();
    }
}
