"""Speech: on the devices (the default) – each Emkay itself, be it a phone,
a tablet, a PC browser or a TV – or in the house.

Every Emkay can do speech itself, in the browser. On a strong machine the
house can do it for all of them instead – better and faster than a phone –
with OpenVoiceOS' own servers (the emkay_home_stt and emkay_home_tts
containers, image speech/). OpenVoiceOS' ovos-stt-plugin-onnx-asr hears,
with a model of its own for each language; Piper speaks. Caddy serves them
at /speech/stt/ and /speech/tts/, for the paired Emkays only (SpeechAuth in
app.py: their HiveMind key).

Which model hears which language is the plugin's choice (its per-language
registry), except where the house knows better (LANG2MODEL, from
docs/danish-speech.md). The choice on the house page is one line: on the
phones or in the house; the house suggests which from the machine. Written
to the speech containers' own config (the emkay_home_speech volume, their
~/.config/mycroft), and they are restarted to pick it up – the house's OVOS
config is left alone.
"""
import json
import logging
import os
import threading
import time
import urllib.request
from pathlib import Path

from . import house, settings

LOG = logging.getLogger("emkay-home")

#: The STT plugin of the house: OpenVoiceOS' onnx-asr (no torch, a model per
#: language, each loaded the first time it is needed).
STT_PLUGIN = "ovos-stt-plugin-onnx-asr"

#: Where the house knows a better model than the plugin's own default, and
#: what it is called on the house page. Measured in docs/danish-speech.md:
#: for Danish the plugin's default (Parakeet v3) gets 30 % of the words
#: wrong, NVIDIA's Danish Parakeet 11 %, and is faster.
LANG2MODEL = {
    "da": "OpenVoiceOS/nvidia-parakeet-rnnt-110m-da-dk-onnx",
}
MODEL_NAMES = {
    "OpenVoiceOS/nvidia-parakeet-rnnt-110m-da-dk-onnx": "NVIDIA Parakeet, Danish",
}


# --- the machine ----------------------------------------------------------------

def _cgroup_mem_gb():
    try:
        v = Path("/sys/fs/cgroup/memory.max").read_text().strip()
        return None if v == "max" else int(v) / 2**30
    except (OSError, ValueError):
        return None


def hardware():
    """What the house runs on, as far as this container can see: cores (an
    LXC's limit included), memory, and an NVIDIA GPU."""
    try:
        cores = len(os.sched_getaffinity(0))
    except AttributeError:
        cores = os.cpu_count() or 1
    mem = None
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                mem = int(line.split()[1]) / 2**20
                break
    except (OSError, ValueError):
        pass
    limit = _cgroup_mem_gb()
    if limit and (mem is None or limit < mem):
        mem = limit
    return {"cores": cores, "mem_gb": round(mem, 1) if mem else None,
            "gpu": Path("/dev/nvidia0").exists()}


def preset(hw):
    """Where the house suggests speech should be on this machine. The house's
    models need little (NVIDIA's Danish Parakeet: 0.7 GB, a fifth of a
    second a command on four cores), so a machine with a few cores and
    memory to spare does better than a phone."""
    cores, mem = hw["cores"], hw["mem_gb"] or 0
    return {"where": "house" if cores >= 2 and mem >= 4 else "phones"}


# --- the choice -----------------------------------------------------------------

def hears(lang):
    """What hears this language in the house, for the house page."""
    base = (lang or "en-us").split("-")[0].lower()
    model = LANG2MODEL.get(base)
    return MODEL_NAMES.get(model, model) if model else "OpenVoiceOS onnx-asr"


def current():
    st = house.load_state()
    sp = st.get("speech") or {}
    hw = hardware()
    return {"where": sp.get("where", "phones"), "suggested": preset(hw), "hardware": hw,
            "hears": hears(st.get("lang"))}


def choose(where, model=None):
    """model: no longer chosen here (the plugin picks one per language); taken
    and ignored, for older pages."""
    if where not in ("phones", "house"):
        raise ValueError("where: phones or house")
    st = house.load_state()
    sp = st.get("speech") or {}
    sp["where"] = where
    sp.pop("model", None)
    st["speech"] = sp
    house.save_state(st)
    apply()


def in_house():
    return (house.load_state().get("speech") or {}).get("where") == "house"


def apply(restart=True):
    """The choice into the speech containers' config, and restart them."""
    c = current()
    lang = house.load_state().get("lang") or "en-us"
    conf = {
        "lang": lang,
        # cpu_models_only: no 1B-parameter models, and the plugin's own
        # fallback (loaded when it starts) is Whisper base, not Canary 1B
        "stt": {"module": STT_PLUGIN, STT_PLUGIN: {"quantization": "int8", "cpu_models_only": True,
                                                   "lang2model": LANG2MODEL}},
        "tts": {"module": "ovos-tts-plugin-piper", "ovos-tts-plugin-piper": {}},
    }
    d = settings.SPEECH_CONFIG
    try:
        d.mkdir(parents=True, exist_ok=True)
        (d / "mycroft.conf").write_text(json.dumps(conf, indent=2))
        flag = d / "in-the-house"
        if c["where"] == "house":
            flag.write_text("1\n")
        else:
            flag.unlink(missing_ok=True)
    except OSError as e:
        LOG.warning("could not write the speech settings: %s", e)
        return
    _warm.clear()
    if restart:
        for name in ("emkay_home_stt", "emkay_home_tts"):
            house.request_restart(name)
    if c["where"] == "house":
        warm_up()
    LOG.info("speech %s", f"in the house ({c['hears']} for {lang})" if c["where"] == "house" else "on the phones")


def lang_changed():
    """The house's language is Piper's default voice: restart the servers."""
    if in_house():
        apply()


# --- how they are doing ---------------------------------------------------------

def _up(port):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/status", timeout=1.5) as r:
            return r.status == 200
    except OSError:
        return False


# The plugin loads a language's model the first time it hears that language
# (the first time ever, it downloads it). So the house has it hear a second
# of quiet in its own language before it says "ready" – the first Emkay to
# ask then doesn't wait for a download.
_warm = threading.Event()
_warming = threading.Lock()


def warm_up():
    def run():
        if not _warming.acquire(blocking=False):
            return
        try:
            lang = house.load_state().get("lang") or "en-us"
            quiet = bytes(32000)   # one second of 16 kHz 16-bit silence
            url = f"http://127.0.0.1:{settings.STT_PORT}/stt?lang={lang}&sample_rate=16000&sample_width=2"
            deadline = time.time() + 1800
            while in_house() and time.time() < deadline:
                try:
                    urllib.request.urlopen(urllib.request.Request(url, data=quiet, method="POST"), timeout=900).read()
                    _warm.set()
                    LOG.info("the house hears %s", lang)
                    return
                except OSError:
                    time.sleep(5)
        finally:
            _warming.release()
    threading.Thread(target=run, name="speech-warm-up", daemon=True).start()


def status():
    """off (on the phones) / starting (loading or downloading the models –
    the first time a few minutes) / ready."""
    if not in_house():
        return {"state": "off"}
    stt, tts = _up(settings.STT_PORT), _up(settings.TTS_PORT)
    if stt and tts and not _warm.is_set():
        warm_up()   # e.g. after emkay_home itself was restarted
    ready = stt and tts and _warm.is_set()
    return {"state": "ready" if ready else "starting", "stt": stt, "tts": tts}


def for_emkay(host):
    """What a paired Emkay needs to use the house's speech (the pairing link
    carries it, and /api/house-info answers it later), or None."""
    if not in_house():
        return None
    port = "" if settings.HTTPS_PORT == 443 else f":{settings.HTTPS_PORT}"
    base = f"https://{host}{port}/speech"
    return {"stt": f"{base}/stt/stt", "tts": f"{base}/tts", "auth": "hivemind-key"}
