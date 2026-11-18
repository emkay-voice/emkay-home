#!/usr/bin/env python3
"""Speech in the house, tried out the way an Emkay would use it: turn it on
on the house page, wait for Whisper and Piper, then – as the paired Emkay
from tools/smoke.py – have the house say something and hear it back.

    python tools/speak.py 192.168.1.10 pairing.json            # en-us, Whisper tiny
    python tools/speak.py 192.168.1.10 pairing.json --model small --say "hvad er klokken" --lang da-dk

Prints how long the house took to speak and to hear. Standard library only.
"""
import argparse
import base64
import http.cookiejar
import json
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


def main():
    p = argparse.ArgumentParser()
    p.add_argument("host")
    p.add_argument("pairing", help="what tools/smoke.py printed")
    p.add_argument("--https", type=int, default=443)
    p.add_argument("--password", default="emkay-smoke")
    p.add_argument("--model", default="tiny")
    p.add_argument("--lang", default="en-us")
    p.add_argument("--say", default="what time is it")
    p.add_argument("--voice", default="en_US-lessac-medium",
                   help="the Piper voice, as Emkay asks for it (its voiceFor)")
    p.add_argument("--expect", default="time", help="a word the house must hear back")
    p.add_argument("--timeout", type=int, default=900, help="seconds to wait for the models")
    a = p.parse_args()
    pairing = json.load(open(a.pairing))
    ctx = ssl.create_default_context(cafile=pairing["ca"])
    base = f"https://{a.host}:{a.https}"

    def step(msg):
        print(f"• {msg}", file=sys.stderr)

    web = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx),
                                      urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    phone = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))

    def api(path, body=None):
        req = urllib.request.Request(base + path, method="GET" if body is None else "POST",
                                     data=None if body is None else json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        with web.open(req, timeout=15) as r:
            return json.loads(r.read() or b"{}")

    key = {"Authorization": f"Bearer {pairing['link']['key']}"}

    step("log in, speech in the house")
    api("/api/login", {"password": a.password})
    api("/api/speech", {"where": "house", "model": a.model})

    step(f"wait for Whisper ({a.model}) and Piper")
    t0 = time.time()
    while True:
        s = api("/api/speech")
        if s["status"]["state"] == "ready":
            break
        if time.time() - t0 > a.timeout:
            raise SystemExit(f"speech never got ready: {s['status']}")
        time.sleep(5)
    step(f"  ready after {time.time() - t0:.0f} s – {s['hardware']}")

    step("the Emkay asks the house where speech is")
    with phone.open(urllib.request.Request(base + "/api/house-info", headers=key), timeout=15) as r:
        house = json.loads(r.read())
    info = house["speech"]
    assert house["panel"].startswith("https://"), house
    assert info and info["stt"] and info["tts"], info

    step("a stranger is turned away")
    tts_url = info["tts"] + "/v2/synthesize?" + urllib.parse.urlencode({"utterance": a.say, "lang": a.lang, "voice": a.voice})
    try:
        phone.open(tts_url, timeout=15)
        raise AssertionError("speech answered without a key")
    except urllib.error.HTTPError as e:
        assert e.code == 401, e.code

    step(f"the house says “{a.say}”")
    t1 = time.time()
    with phone.open(urllib.request.Request(tts_url, headers=key), timeout=120) as r:
        wav = r.read()
    t_tts = time.time() - t1
    assert wav[:4] == b"RIFF", wav[:40]

    step("and hears it back")
    t2 = time.time()
    body = json.dumps({"audio_b64": base64.b64encode(wav).decode(), "lang": a.lang}).encode()
    req = urllib.request.Request(info["stt"] + "/json", data=body,
                                 headers={**key, "Content-Type": "application/json"})
    with phone.open(req, timeout=120) as r:
        heard = json.loads(r.read())
    t_stt = time.time() - t2
    step(f"  heard “{heard['text']}”")
    assert a.expect.lower() in heard["text"].lower(), heard

    print(json.dumps({"model": a.model, "said": a.say, "heard": heard["text"],
                      "tts_seconds": round(t_tts, 2), "stt_seconds": round(t_stt, 2),
                      "hardware": s["hardware"]}))


if __name__ == "__main__":
    main()
