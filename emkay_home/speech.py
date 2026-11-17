"""Speech: on the phones (the default), or in the house.

Every Emkay can do speech itself, in the browser. On a strong machine the
house can do it for all of them instead – better and faster than a phone –
with OpenVoiceOS' own servers (the emkay_home_stt and emkay_home_tts
containers, image speech/): Whisper hears, Piper speaks. Caddy serves them at
/speech/stt/ and /speech/tts/, for the paired Emkays only (SpeechAuth in
app.py: their HiveMind key).

The choice is one line on the house page. Which Whisper model fits is the
house's to work out from the machine (`preset`), so nobody picks plugins;
it can still be changed there. Written here to the speech containers' own
config (the emkay_home_speech volume, their ~/.config/mycroft), and they are
restarted to pick it up – the house's OVOS config is left alone.
"""
import json
import logging
import os
import urllib.request
from pathlib import Path

from . import house, settings

LOG = logging.getLogger("emkay-home")

#: Whisper models, smallest first (faster-whisper names). "large-v3-turbo"
#: wants a GPU (step 2 of emkay-home#13).
MODELS = ("tiny", "base", "small", "medium", "large-v3-turbo")


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
    """What the house suggests for this machine: where speech should be, and
    which Whisper model. A phone does well enough on its own, so the house
    only takes over when it clearly does better."""
    cores, mem = hw["cores"], hw["mem_gb"] or 0
    if cores >= 8 and mem >= 12:
        return {"where": "house", "model": "medium"}
    if cores >= 4 and mem >= 6:
        return {"where": "house", "model": "small"}
    return {"where": "phones", "model": "base" if cores >= 2 else "tiny"}


# --- the choice -----------------------------------------------------------------

def current():
    st = house.load_state().get("speech") or {}
    hw = hardware()
    p = preset(hw)
    return {"where": st.get("where", "phones"), "model": st.get("model") or p["model"],
            "suggested": p, "hardware": hw, "models": list(MODELS)}


def choose(where, model=None):
    if where not in ("phones", "house") or (model and model not in MODELS):
        raise ValueError("where: phones or house; model: one of MODELS")
    st = house.load_state()
    sp = st.get("speech") or {}
    sp["where"] = where
    if model:
        sp["model"] = model
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
        "stt": {"ovos-stt-plugin-fasterwhisper": {
            "model": c["model"], "compute_type": "int8", "beam_size": 5,
            "cpu_threads": max(1, c["hardware"]["cores"]), "vad_filter": True,
        }},
        "tts": {"ovos-tts-plugin-piper": {}},
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
    if restart:
        for name in ("emkay_home_stt", "emkay_home_tts"):
            house.request_restart(name)
    LOG.info("speech %s (Whisper %s)", "in the house" if c["where"] == "house" else "on the phones", c["model"])


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


def status():
    """off (on the phones) / starting (loading or downloading a model – the
    first time a few minutes) / ready."""
    if not in_house():
        return {"state": "off"}
    stt, tts = _up(settings.STT_PORT), _up(settings.TTS_PORT)
    return {"state": "ready" if stt and tts else "starting", "stt": stt, "tts": tts}


def for_emkay(host):
    """What a paired Emkay needs to use the house's speech (the pairing link
    carries it, and /api/house-info answers it later), or None."""
    if not in_house():
        return None
    port = "" if settings.HTTPS_PORT == 443 else f":{settings.HTTPS_PORT}"
    base = f"https://{host}{port}/speech"
    return {"stt": f"{base}/stt/stt", "tts": f"{base}/tts", "auth": "hivemind-key"}
