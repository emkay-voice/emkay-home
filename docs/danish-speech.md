# Danish speech in the house

Which speech recognition model the house should use for Danish when speech
is in the house (#13). Measured with [`tools/stt_bench.py`](../tools/stt_bench.py)
in the **Danish STT bench** workflow on GitHub's runners (4 CPUs, 16 GB, no
GPU), November 2026.

- **FLEURS**: 40 sentences of real people reading (Google's FLEURS, da_dk test).
- **Asked**: 18 things people say to an Emkay ("hvad er klokken", "tænd
  lyset i stuen" …), spoken by Piper's Danish voice, with half a second of
  quiet first, as a recording after the wake word has.

Word error rate (lower is better; "kl." and digits count as the words said),
and seconds per clip on 4 CPUs:

| model | real speech | asked | s / command | peak RAM | "hvad er klokken" |
|---|---|---|---|---|---|
| **Røst + KenLM** (CoRal, wav2vec2 315M with its language model) | 15.4 % | **12.0 %** | **0.5 s** | 4.0 GB | “hvad er klokken” |
| Whisper large-v3-turbo | **13.1 %** | 12.0 % | 10.3 s | 1.9 GB | “Hverglocken.” |
| Edda v0.2 (Danish turbo, Apache 2.0) | 14.3 % | 19.3 % | 10.4 s | 1.3 GB | “hvad er klokken” |
| Whisper medium | 20.2 % | 21.7 % | 4.3 s | 2.0 GB | “Vær klokken.” |
| Røst, no language model (as on the phone) | 21.2 % | 28.9 % | 0.3 s | 2.3 GB | “hver e glokken” |
| Whisper small | 34.4 % | 25.3 % | 1.5 s | 0.8 GB | “Hver klokken?” |

## What it means

- **On a CPU, Røst with its language model is the one.** It is as accurate
  as the large models and twenty times faster: half a second for a command,
  where Whisper large-v3-turbo and Edda take ten. It is the same model the
  phone uses (emkay-voice/stt-models, docs/danish.md), plus the KenLM
  language model a phone can't carry, which takes it from 21 % to 15 % on
  real speech and gets "hvad er klokken" right.
- **Whisper small and medium are not for Danish.** "Small" is where
  "hvad er kloppen" comes from.
- **Whisper large-v3-turbo and Edda are for a GPU.** They hear as well as or
  better than Røst, but take ten seconds a command on four CPUs. On a GPU
  they take a fraction of a second; then Edda, trained on Danish, is the
  natural choice (it still drops a first word now and then on these clips).
- Røst + KenLM needs about 4 GB while running and a minute to load when the
  house starts – fine for a house, not for a small LXC with 2 GB.

So the house picks the model by language as well as by machine: Danish on a
CPU → Røst + KenLM; Danish on a GPU → Edda; other languages → Whisper as
before.
