# Third-Party Models & Licenses

Yumii bundles one model (Silero VAD) and mirrors one family (the
faster-whisper models). Every other model below is downloaded from its
upstream source the first time you choose the feature that needs it.
Most are permissively licensed (MIT, Apache-2.0, BSD-2-Clause); the two
NVIDIA Nemotron models are under NVIDIA's own model licenses, which
allow commercial use but carry their own terms — read them before
redistributing those weights. The notices below give the attribution
these licenses ask for.

| Model | Role | Source | License |
|-------|------|--------|---------|
| **Silero VAD** | Voice activity detection | snakers4/silero-vad (bundled: `src/yumii/assets/models/silero_vad.onnx`) | MIT |
| **faster-whisper** (tiny/base/small) | Speech-to-text (default) | Systran/faster-whisper-* (mirrored to this repo's `whisper-models-v1` release) | MIT |
| **Kokoro-82M** | Text-to-speech (default) | thewh1teagle/kokoro-onnx (downloaded from their GitHub release) | Apache-2.0 |
| **Smart Turn v3** | End-of-turn detection | pipecat-ai/smart-turn-v3 (downloaded from Hugging Face) | BSD-2-Clause |
| **Nemotron Speech Streaming EN 0.6B** | Streaming speech-to-text (opt-in) | NVIDIA; sherpa-onnx int8 build from the k2-fsa/sherpa-onnx `asr-models` release | NVIDIA Open Model License |
| **Nemotron 3.5 ASR Streaming 0.6B** | Multilingual streaming speech-to-text (opt-in) | NVIDIA; sherpa-onnx int8 build from the k2-fsa/sherpa-onnx `asr-models` release | OpenMDW-1.1 |
| **Moonshine v2** (base, English) | Lightweight speech-to-text (opt-in) | Moonshine AI; sherpa-onnx build from the k2-fsa/sherpa-onnx `asr-models` release | MIT |
| **Vosk** (small-en-us-0.15, en-us-0.22-lgraph) | Offline streaming speech-to-text (opt-in) | alphacephei.com/vosk/models | Apache-2.0 |

## faster-whisper (Systran) — MIT

The faster-whisper models are CTranslate2 conversions of OpenAI's
Whisper models by SYSTRAN, released under the MIT License. Yumii mirrors
them to its own GitHub release (`whisper-models-v1`) so they can be
fetched from GitHub instead of HuggingFace's CDN; each mirrored archive
includes the upstream README/attribution. See
<https://huggingface.co/Systran/faster-whisper-base>. Underlying Whisper
is by OpenAI (<https://github.com/openai/whisper>).

## Kokoro-82M — Apache-2.0

Kokoro-82M is released under the Apache License 2.0. Yumii downloads the
ONNX build from the `kokoro-onnx` GitHub releases. See
<https://huggingface.co/hexgrad/Kokoro-82M>.

## Silero VAD — MIT

Silero VAD is released under the MIT License. The ONNX model is bundled
in the Yumii package. See <https://github.com/snakers4/silero-vad>.

## Smart Turn v3 (Pipecat) — BSD-2-Clause

Smart Turn v3 is Pipecat's end-of-turn model, released under the
BSD 2-Clause License. Yumii downloads the ONNX model from Hugging Face on
first use. See <https://github.com/pipecat-ai/smart-turn> and
<https://huggingface.co/pipecat-ai/smart-turn-v3>.

## NVIDIA Nemotron speech models — NVIDIA Open Model License / OpenMDW-1.1

Nemotron Speech Streaming EN 0.6B is licensed by NVIDIA Corporation
under the NVIDIA Open Model License; Nemotron 3.5 ASR Streaming 0.6B is
released under OpenMDW-1.1. Both are opt-in: Yumii downloads the
sherpa-onnx int8 conversions (k2-fsa/sherpa-onnx, `asr-models` release)
only when you select them. The governing terms are on NVIDIA's model
cards: <https://huggingface.co/nvidia/nemotron-speech-streaming-en-0.6b>
and <https://huggingface.co/nvidia/nemotron-3.5-asr-streaming-0.6b>.

## Moonshine v2 — MIT

Moonshine's English models are released by Moonshine AI under the MIT
License (the license file ships inside the downloaded archive). Yumii
downloads the sherpa-onnx build on first use. See
<https://github.com/moonshine-ai/moonshine>.

## Vosk models — Apache-2.0

The Vosk English models are released by Alpha Cephei under the Apache
License 2.0. Yumii downloads them from <https://alphacephei.com/vosk/models>
on first use.

---

Speech models run on [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx)
(Apache-2.0). The full MIT, Apache-2.0 and BSD-2-Clause license texts are
available at <https://opensource.org/license/mit>,
<https://www.apache.org/licenses/LICENSE-2.0> and
<https://opensource.org/license/bsd-2-clause>. Yumii's own code is MIT —
see [LICENSE](LICENSE).
