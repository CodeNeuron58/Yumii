# Third-Party Models & Licenses

Yumii downloads or bundles several open-source models. Each is
redistributed under a permissive license; the notices below satisfy the
attribution those licenses require.

| Model | Role | Source | License |
|-------|------|--------|---------|
| **Silero VAD** | Voice activity detection | snakers4/silero-vad (bundled: `src/yumii/assets/models/silero_vad.onnx`) | MIT |
| **faster-whisper** (tiny/base/small) | Speech-to-text | Systran/faster-whisper-* (mirrored to this repo's `whisper-models-v1` release) | MIT |
| **Kokoro-82M** | Text-to-speech | thewh1teagle/kokoro-onnx (downloaded from their GitHub release) | Apache-2.0 |

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

---

The full MIT and Apache-2.0 license texts are available at
<https://opensource.org/license/mit> and
<https://www.apache.org/licenses/LICENSE-2.0>. Yumii's own code is MIT —
see [LICENSE](LICENSE).
