#!/usr/bin/env python3
"""How well and how fast speech recognition models hear Danish – to pick
what the house uses for speech in Danish (emkay-home#13).

Runs in CI (.github/workflows/stt-bench.yml), not on a machine people work on:
each model loads up to a few GB.

    stt_bench.py clips OUT        Danish clips: what an Emkay is asked
                                  (Piper's Danish voice, via the house's own
                                  TTS server on :8591) and real speech
                                  (FLEURS da_dk test), with what was said
    stt_bench.py run MODEL CLIPS  one model over the clips; prints JSON
    stt_bench.py report FILES…    a Markdown table of the results

MODEL is fw:<name or dir> (faster-whisper, int8 on CPU – what the house's
ovos-stt-plugin-fasterwhisper runs) or w2v:<huggingface id> (a wav2vec2 CTC
model, as Røst; transformers on CPU).
"""
import json
import os
import re
import resource
import subprocess
import sys
import tarfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

#: What people ask an Emkay, in Danish.
PHRASES = [
    "hvad er klokken", "hvordan bliver vejret i morgen", "sæt en timer på fem minutter",
    "tænd lyset i stuen", "sluk lyset i køkkenet", "spil noget musik", "skru ned for lyden",
    "hvad er to plus to", "fortæl mig en vittighed", "hvem er statsminister i Danmark",
    "hvor langt er der til månen", "mind mig om at købe mælk i morgen",
    "hvad står der i min kalender i dag", "hvad hedder du", "hvad er hovedstaden i Norge",
    "sæt en alarm klokken syv", "hvad er temperaturen udenfor", "godnat",
]
FLEURS = "https://huggingface.co/datasets/google/fleurs/resolve/main/data/da_dk/"
FLEURS_CLIPS = 40


#: Whisper writes numbers and "kl." the way a newspaper does; what was said
#: is the same.
SAME = {"0": "nul", "1": "en", "2": "to", "3": "tre", "4": "fire", "5": "fem", "6": "seks",
        "7": "syv", "8": "otte", "9": "ni", "10": "ti", "11": "elleve", "12": "tolv",
        "kl": "klokken", "et": "en", "imorgen": "i morgen"}


def norm(s):
    s = s.lower().replace("-", " ")
    s = re.sub(r"[^\w\sæøå]", " ", s)
    return " ".join(SAME.get(w, w) for w in s.split())


def wer(ref, hyp):
    r, h = norm(ref).split(), norm(hyp).split()
    d = list(range(len(h) + 1))
    for i, rw in enumerate(r, 1):
        prev, d[0] = d[0], i
        for j, hw in enumerate(h, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (rw != hw))
    return d[len(h)], max(len(r), 1)


# --- clips ------------------------------------------------------------------------

def clips(out):
    out = Path(out)
    (out / "asked").mkdir(parents=True, exist_ok=True)
    (out / "fleurs").mkdir(parents=True, exist_ok=True)
    index = []
    for i, text in enumerate(PHRASES):
        q = urllib.parse.urlencode({"utterance": text, "lang": "da-dk", "voice": "da_DK-talesyntese-medium"})
        wav = urllib.request.urlopen(f"http://127.0.0.1:8591/v2/synthesize?{q}", timeout=120).read()
        f = out / "asked" / f"{i:02d}.wav"
        f.write_bytes(wav)
        index.append({"set": "asked (Piper)", "file": str(f.relative_to(out)), "text": text})
    try:
        tsv = urllib.request.urlopen(FLEURS + "test.tsv", timeout=120).read().decode()
        rows = [r.split("\t") for r in tsv.splitlines() if r.strip()]
        want = {r[1]: r[2] for r in rows[:FLEURS_CLIPS * 3]}   # file → raw transcription
        tgz = out / "fleurs-test.tar.gz"
        urllib.request.urlretrieve(FLEURS + "audio/test.tar.gz", tgz)
        n = 0
        with tarfile.open(tgz) as tf:
            for m in tf:
                name = os.path.basename(m.name)
                if m.isfile() and name in want and n < FLEURS_CLIPS:
                    (out / "fleurs" / name).write_bytes(tf.extractfile(m).read())
                    index.append({"set": "FLEURS (real speech)", "file": f"fleurs/{name}", "text": want[name]})
                    n += 1
        tgz.unlink()
        print(f"FLEURS: {n} clips", file=sys.stderr)
    except Exception as e:  # noqa: BLE001 - the asked clips are enough to go on
        print(f"FLEURS could not be fetched: {e}", file=sys.stderr)
    (out / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1))
    print(f"{len(index)} clips in {out}")


# --- models -----------------------------------------------------------------------

def load(model):
    kind, name = model.split(":", 1)
    if kind == "fw":
        from faster_whisper import WhisperModel
        m = WhisperModel(name, device="cpu", compute_type="int8", cpu_threads=os.cpu_count() or 4)

        def hear(audio):
            segs, _ = m.transcribe(audio, language="da", beam_size=5, vad_filter=False)
            return " ".join(s.text for s in segs).strip()
        return hear
    if kind == "w2v":
        import torch
        from transformers import AutoFeatureExtractor, AutoModelForCTC, AutoTokenizer
        torch.set_num_threads(os.cpu_count() or 4)
        # plain CTC decoding, as Emkay does on the phone (no language model)
        fe = AutoFeatureExtractor.from_pretrained(name)
        tok = AutoTokenizer.from_pretrained(name)
        m = AutoModelForCTC.from_pretrained(name, torch_dtype=torch.float32).eval()

        def hear(audio):
            x = fe(audio, sampling_rate=16000, return_tensors="pt")
            with torch.inference_mode():
                ids = m(**x).logits.argmax(-1)
            return tok.batch_decode(ids)[0].strip()
        return hear
    raise SystemExit(f"unknown model kind: {model}")


def decode_audio(path, sampling_rate=16000):
    """A sound file as float32 mono at 16 kHz (soundfile, not PyAV: its
    newest release and faster-whisper's decode_audio don't get along)."""
    import numpy as np
    import soundfile as sf
    a, rate = sf.read(path, dtype="float32", always_2d=True)
    a = a.mean(axis=1)
    if rate != sampling_rate:
        n = int(len(a) * sampling_rate / rate)
        a = np.interp(np.linspace(0, len(a) - 1, n), np.arange(len(a)), a).astype(np.float32)
    return a


def run(model, clipdir):
    clipdir = Path(clipdir)
    index = json.loads((clipdir / "index.json").read_text())
    t0 = time.time()
    hear = load(model)
    load_s = time.time() - t0
    hear(decode_audio(str(clipdir / index[0]["file"]), sampling_rate=16000))   # warm up
    per_set, out = {}, []
    for c in index:
        audio = decode_audio(str(clipdir / c["file"]), sampling_rate=16000)
        t = time.time()
        text = hear(audio)
        took = time.time() - t
        e, n = wer(c["text"], text)
        s = per_set.setdefault(c["set"], {"errors": 0, "words": 0, "audio_s": 0.0, "time_s": 0.0, "clips": 0})
        s["errors"] += e; s["words"] += n; s["audio_s"] += len(audio) / 16000; s["time_s"] += took; s["clips"] += 1
        out.append({**c, "heard": text, "seconds": round(took, 2)})
        print(f"{took:5.2f}s  {c['text'][:50]!r} → {text[:60]!r}", file=sys.stderr)
    print(json.dumps({
        "model": model, "load_s": round(load_s, 1),
        "peak_rss_gb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20, 2),
        "cpus": os.cpu_count(),
        "sets": {k: {**v, "wer": round(100 * v["errors"] / v["words"], 1),
                     "rtf": round(v["time_s"] / v["audio_s"], 3),
                     "per_clip_s": round(v["time_s"] / v["clips"], 2)} for k, v in per_set.items()},
        "clips": out,
    }, ensure_ascii=False))


def rescore(r):
    """The word error rate again from what was heard (so a better norm()
    applies to results already made)."""
    for name, st in r["sets"].items():
        e = n = 0
        for c in r["clips"]:
            if c["set"] == name:
                ce, cn = wer(c["text"], c["heard"])
                e += ce; n += cn
        st["wer"] = round(100 * e / max(n, 1), 1)
    return r


def report(files):
    rows = [rescore(json.loads(Path(f).read_text())) for f in files if Path(f).stat().st_size]
    sets = sorted({s for r in rows for s in r["sets"]})
    head = "| model | peak RAM | load | " + " | ".join(f"{s}: WER · s/clip" for s in sets) + " |"
    lines = [head, "|" + "---|" * (3 + len(sets))]
    for r in sorted(rows, key=lambda r: r["sets"].get(sets[-1], {}).get("wer", 999)):
        cells = [f"{r['sets'][s]['wer']} % · {r['sets'][s]['per_clip_s']} s" if s in r["sets"] else "–" for s in sets]
        lines.append(f"| `{r['model']}` | {r['peak_rss_gb']} GB | {r['load_s']} s | " + " | ".join(cells) + " |")
    print(f"Danish speech recognition, {rows[0]['cpus'] if rows else '?'} CPUs, int8 where it applies\n")
    print("\n".join(lines))
    print("\nWhat was heard for “hvad er klokken”:\n")
    for r in rows:
        c = next((c for c in r["clips"] if c["text"] == "hvad er klokken"), None)
        if c:
            print(f"- `{r['model']}`: “{c['heard']}”")


if __name__ == "__main__":
    cmd, *args = sys.argv[1:] or ["help"]
    if cmd == "clips":
        clips(*args)
    elif cmd == "run":
        run(*args)
    elif cmd == "report":
        report(args)
    else:
        print(__doc__)
