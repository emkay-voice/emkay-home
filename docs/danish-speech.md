# Danish speech in the house

Which speech recognition model the house should use for Danish when speech
is in the house (#13). Measured with [`tools/stt_bench.py`](../tools/stt_bench.py)
in the **Danish STT bench** workflow on GitHub's runners (4 CPUs, 16 GB, no
GPU), November 2026.

- **Real speech**: 40 sentences of real people reading (Google's FLEURS, da_dk test).
- **Asked**: 18 things people say to an Emkay ("hvad er klokken", "tænd
  lyset i stuen" …), spoken by Piper's Danish voice, with half a second of
  quiet first, as a recording after the wake word has. Piper mispronounces
  some words itself, and its voice varies a little from run to run, so this
  set is rougher than the real one.

Word error rate (lower is better; "kl." and digits count as the words said),
seconds per clip on 4 CPUs, and memory while running:

| model | real speech | asked | s / sentence | s / command | RAM |
|---|---|---|---|---|---|
| **NVIDIA Parakeet 110M Danish** (OpenVoiceOS' ONNX conversion, `ovos-stt-plugin-onnx-asr`) | **11.0 %** | 14.5 % | **0.5 s** | **0.2 s** | **0.7 GB** |
| Whisper large-v3-turbo (faster-whisper) | 13.1 % | 12–23 % | 11 s | 10 s | 1.8 GB |
| Edda v0.2 (Danish turbo, faster-whisper) | 14.3 % | 19–21 % | 11 s | 11 s | 1.3 GB |
| Røst + KenLM (CoRal, wav2vec2 315M with its language model) | 15.4 % | 12–13 % | 2–4 s | 0.5–0.9 s | 4.0 GB |
| Whisper medium (faster-whisper) | 20 % | 21 % | 6–8 s | 4–5 s | 2.0–2.7 GB |
| Røst, no language model (as on the phone) | 21.2 % | 25–29 % | 2 s | 0.3 s | 2.3 GB |
| Parakeet v3 multilingual (`ovos-stt-plugin-onnx-asr`'s Danish default) | 29.6 % | 24.1 % | 1 s | 0.3 s | 1.8 GB |
| Whisper small (faster-whisper) | 34.4 % | 25–33 % | 2.3 s | 1.5 s | 0.8 GB |

## What it means

- **NVIDIA's Danish Parakeet is the one, on any machine.** It hears real
  speech best of all (11 %), takes half a second for a sentence and a fifth
  of a second for a command, and needs 0.7 GB – it fits even a small LXC.
  OpenVoiceOS has already converted it
  ([OpenVoiceOS/nvidia-parakeet-rnnt-110m-da-dk-onnx](https://huggingface.co/OpenVoiceOS/nvidia-parakeet-rnnt-110m-da-dk-onnx)),
  and the stock **ovos-stt-plugin-onnx-asr** runs it with no torch. So the
  house needs no plugin of its own: it uses that plugin and names this model
  for Danish (`lang2model`).
- **The plugin's own Danish default, Parakeet v3, is not good for Danish**
  (30 %) – so the house names the Danish model rather than relying on the
  default. Worth suggesting upstream later.
- **Whisper small and medium are not for Danish.** "Small" is where
  "hvad er kloppen" comes from.
- Whisper large-v3-turbo, Edda and Røst + KenLM are as good or nearly, but
  ten to twenty times slower on a CPU (or, for Røst + KenLM, six times the
  memory).

So the house hears with OpenVoiceOS' onnx-asr plugin, which already picks a
dedicated model per language (Parakeet / FastConformer fine-tunes for
English, German, Spanish, French, Italian, Dutch, Portuguese, Catalan,
Basque, Galician …), with NVIDIA's Danish Parakeet named for Danish.
