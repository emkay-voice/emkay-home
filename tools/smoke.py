#!/usr/bin/env python3
"""Walk through Emkay Home the way a person would, against a running house:
the welcome page, the certificate, first start, "Add an Emkay", pairing,
the list – and print the pairing link Emkay would open.

    python tools/smoke.py 192.168.1.10                 # ports 80/443
    python tools/smoke.py 192.168.1.10 --http 8080 --https 8443 --password secret1
    python tools/smoke.py 192.168.1.10 --panel 8500    # and the control panel

A house that is already set up needs its --password. Standard library only.
"""
import argparse
import base64
import http.cookiejar
import json
import ssl
import sys
import tempfile
import time
import urllib.parse
import urllib.request


def main():
    p = argparse.ArgumentParser()
    p.add_argument("host")
    p.add_argument("--http", type=int, default=80)
    p.add_argument("--https", type=int, default=443)
    p.add_argument("--password", default="emkay-smoke")
    p.add_argument("--lang", default="en-us")
    p.add_argument("--panel", type=int, help="also the control panel, on this port")
    a = p.parse_args()
    http_base = f"http://{a.host}:{a.http}"
    https_base = f"https://{a.host}:{a.https}"

    def step(msg):
        print(f"• {msg}", file=sys.stderr)

    step("welcome page over http")
    page = urllib.request.urlopen(http_base + "/", timeout=10).read().decode()
    assert "welcome.js" in page, "no welcome page on http"

    step("the house's certificate")
    pem = urllib.request.urlopen(http_base + "/ca.crt", timeout=10).read()
    assert pem.startswith(b"-----BEGIN CERTIFICATE-----"), "no certificate at /ca.crt"
    with tempfile.NamedTemporaryFile("wb", suffix=".crt", delete=False) as f:
        f.write(pem)
    ctx = ssl.create_default_context(cafile=f.name)

    jar = http.cookiejar.CookieJar()
    web = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx),
                                      urllib.request.HTTPCookieProcessor(jar))

    def api(path, body=None):
        req = urllib.request.Request(https_base + path, method="GET" if body is None else "POST",
                                     data=None if body is None else json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        with web.open(req, timeout=15) as r:
            return json.loads(r.read() or b"{}")

    step("https with the house's certificate")
    info = api("/api/info")
    assert info["ca"], "the page doesn't know the certificate"
    step(f"  fingerprint {info['ca']['sha256'][:23]}…")

    if not info["setup_done"]:
        step(f"first start ({a.lang})")
        api("/api/setup", {"lang": a.lang, "password": a.password})
    else:
        step("log in")
        api("/api/login", {"password": a.password})

    step("add an Emkay")
    inv = api("/api/invite", {"name": "Smoke test"})
    assert inv["qr"].lstrip().startswith("<svg"), "no QR code"
    code = urllib.parse.urlparse(inv["url"]).fragment.split("=", 1)[1]
    step(f"  QR code says {inv['url'].split('#')[0]}#t=…")

    step("pair (what the phone does)")
    phone = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
    req = urllib.request.Request(https_base + "/api/redeem", data=json.dumps({"code": code}).encode(),
                                 headers={"Content-Type": "application/json"})
    url = json.loads(phone.open(req, timeout=15).read())["url"]
    link = json.loads(base64.b64decode(urllib.parse.unquote(url.split("#hivemind=", 1)[1])))
    assert link["path"] == "/hivemind" and link["ssl"] and link["key"] and link["password"]
    step(f"  Emkay opens {url.split('#')[0]} – host {link['host']}:{link['port']}{link['path']}")

    step("the code is used up")
    try:
        phone.open(req, timeout=15)
        raise AssertionError("a used code worked again")
    except urllib.error.HTTPError as e:
        assert e.code == 410, e.code
    assert api(f"/api/invite?code={code}")["paired"]

    step("the list")
    clients = api("/api/clients")["clients"]
    me = [c for c in clients if c["name"] == "Smoke test"]
    assert me, "the new Emkay is not in the list"

    if a.panel:
        panel_base = f"https://{a.host}:{a.panel}"

        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kw):
                return None

        step("control panel: a stranger is sent to sign in")
        stranger = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx), NoRedirect)
        try:
            stranger.open(panel_base + "/", timeout=15)
            raise AssertionError("the panel opened without signing in")
        except urllib.error.HTTPError as e:
            assert e.code in (302, 303, 307), e.code
            assert "next=panel" in e.headers.get("Location", ""), e.headers.get("Location")

        step("control panel: signed in, it opens")
        # the panel may still be starting (Caddy answers 502 until it is up)
        for _ in range(60):
            try:
                with web.open(panel_base + "/api/status", timeout=30) as r:
                    assert r.status == 200, r.status
                    json.loads(r.read())
                break
            except urllib.error.HTTPError as e:
                if e.code != 502:
                    raise
                time.sleep(2)
        else:
            raise AssertionError("the control panel never came up")
        with web.open(panel_base + "/", timeout=30) as r:
            assert b'id="emkay-theme"' in r.read(), "the panel is not in Emkay's colours"

    print(json.dumps({"link": link, "ca": f.name, "client_id": me[-1]["id"]}))


if __name__ == "__main__":
    main()
