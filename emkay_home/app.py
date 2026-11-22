"""The page: first start, "Add an Emkay", the paired Emkays, the language.

Only Caddy talks to it (it listens on localhost). Caddy says which way the
request came in (X-Forwarded-Proto): over plain http the house only shows
the welcome page – how to trust the house's certificate – and the
certificate itself; everything else is https.

Pairing: "Add an Emkay" makes a one-time code (10 minutes) and shows it as a
QR code, http://<house>/#t=<code>. The code is in the fragment, which the
browser never sends, so it doesn't cross the network in the clear. The
welcome page checks that the phone trusts the house (or helps it to), then
goes on to https://<house>/pair#t=<code>; that page trades the code for a
new hivemind-core client and opens Emkay with the pairing link
(#hivemind=…). Nobody sees a key or a password, and nothing is mailed.
"""
import asyncio
import base64
import json
import logging
import secrets
import time
from pathlib import Path

import tornado.web

from . import ha, hive, house, panel, settings, site, speech

LOG = logging.getLogger("emkay-home")
WEB = Path(__file__).parent / "web"
LOCALE = Path(__file__).parent / "locale"

SESSIONS = {}   # token -> expiry
INVITES = {}    # code -> {"name", "expires", "paired"}
SESSION_SECONDS = 7 * 24 * 3600


def _prune():
    now = time.time()
    for d, key in ((SESSIONS, None), (INVITES, "expires")):
        for k in [k for k, v in d.items() if (v if key is None else v[key]) < now]:
            del d[k]


class Base(tornado.web.RequestHandler):
    def set_default_headers(self):
        self.set_header("Cache-Control", "no-store")
        self.set_header("X-Content-Type-Options", "nosniff")
        self.set_header("Referrer-Policy", "no-referrer")

    @property
    def https(self):
        return self.request.headers.get("X-Forwarded-Proto", "http") == "https"

    @property
    def host(self):
        """The house as the browser named it (without port); a loopback name
        is no use on a phone, so then the LAN address."""
        h = self.request.host_name
        return house.lan_ip() if house.is_loopback(h) else h

    def body(self):
        try:
            return json.loads(self.request.body or b"{}")
        except ValueError:
            raise tornado.web.HTTPError(400)

    def get_current_user(self):
        _prune()
        tok = self.get_cookie("emkay_home")
        return tok if tok and tok in SESSIONS else None

    def login(self):
        tok = secrets.token_urlsafe(32)
        SESSIONS[tok] = time.time() + SESSION_SECONDS
        self.set_cookie("emkay_home", tok, httponly=True, secure=True, samesite="Strict",
                        expires_days=SESSION_SECONDS / 86400)

    def need_https(self):
        if not self.https:
            raise tornado.web.HTTPError(403, reason="https only")

    def need_login(self):
        self.need_https()
        if not self.current_user:
            raise tornado.web.HTTPError(401)

    def page(self, name):
        self.set_header("Content-Type", "text/html; charset=utf-8")
        self.set_header("Content-Security-Policy",
                        "default-src 'self'; img-src 'self' data:; style-src 'self'; "
                        "connect-src 'self' https:; "
                        # the house's own Emkay may show this page (signing in on the
                        # way to the control panel, inside Emkay) – nobody else
                        f"frame-ancestors 'self' https://{self.request.host_name}:*")
        self.write((WEB / name).read_bytes())


class Root(Base):
    def get(self):
        self.page("index.html" if self.https else "welcome.html")


class Pair(Base):
    def get(self):
        if not self.https:
            return self.redirect("/")   # the fragment (#t=…) stays in the browser
        self.page("pair.html")


def locale_texts():
    """{lang: {key: text}} from locale/<lang>/<key>.dialog – the layout of an
    OVOS skill's dialogs, as in Emkay (tools/build_site.py there), so the
    same translation tooling reads both. The first line is the text."""
    out = {}
    for d in sorted(LOCALE.iterdir()):
        if d.is_dir():
            out[d.name] = {f.name[:-len(".dialog")]: f.read_text(encoding="utf-8").splitlines()[0].strip()
                           for f in sorted(d.glob("*.dialog"))}
    return out


TEXTS_JSON = json.dumps(locale_texts(), ensure_ascii=False).encode()


class Texts(Base):
    def get(self):
        self.set_header("Content-Type", "application/json; charset=utf-8")
        self.write(TEXTS_JSON)


class PanelAuth(Base):
    """Caddy's forward_auth for the control panel (panel.py): signed in to
    Emkay Home → 200 with the panel's token for Caddy to pass on; not → to
    the house page to sign in, and back."""
    def get(self):
        if self.https and self.current_user and panel.token():
            self.set_header("Authorization", f"Bearer {panel.token()}")
            self.set_status(200)
            return
        port = "" if settings.HTTPS_PORT == 443 else f":{settings.HTTPS_PORT}"
        # where the browser was going on the panel, so it gets there after
        # signing in (a path only)
        uri = self.request.headers.get("X-Forwarded-Uri", "/")
        uri = uri if uri.startswith("/") and not uri.startswith("//") else "/"
        q = tornado.escape.url_escape(uri, plus=False)
        self.redirect(f"https://{self.request.host_name}{port}/?next=panel&uri={q}")


class Ping(Base):
    """The welcome page fetches this over https to see whether the phone
    trusts the house's certificate yet."""
    def get(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_status(204)


class TlsAsk(Base):
    """Caddy's on-demand TLS asks here before it makes a certificate."""
    def get(self):
        ok = house.may_have_certificate(self.get_query_argument("domain", ""))
        self.set_status(200 if ok else 403)


class Info(Base):
    def get(self):
        st = house.load_state()
        pem = house.ca_pem()
        self.write({
            "setup_done": bool(st.get("password")),
            "logged_in": bool(self.current_user),
            "lang": st.get("lang"),
            "langs": settings.LANGS,
            "http_port": settings.HTTP_PORT,
            "https_port": settings.HTTPS_PORT,
            "panel_port": settings.PANEL_PORT,
            "ca": {"sha256": house.ca_fingerprint(pem)} if pem else None,
        })


class Setup(Base):
    """First start: the language and a password for the house page."""
    def post(self):
        self.need_https()
        st = house.load_state()
        if st.get("password"):
            raise tornado.web.HTTPError(409)
        b = self.body()
        pw, lang = str(b.get("password", "")), b.get("lang")
        if len(pw) < 6 or lang not in settings.LANGS:
            raise tornado.web.HTTPError(400)
        house.set_password(st, pw)
        st["lang"] = lang
        house.save_state(st)
        house.set_ovos_lang(lang)
        speech.lang_changed()
        self.login()
        self.write({"ok": True})


class Login(Base):
    async def post(self):
        self.need_https()
        await asyncio.sleep(0.5)   # a little friction for guessing
        if not house.check_password(house.load_state(), str(self.body().get("password", ""))):
            raise tornado.web.HTTPError(403)
        self.login()
        self.write({"ok": True})


class Logout(Base):
    def post(self):
        SESSIONS.pop(self.get_cookie("emkay_home") or "", None)
        self.clear_cookie("emkay_home")
        self.write({"ok": True})


class Lang(Base):
    def post(self):
        self.need_login()
        lang = self.body().get("lang")
        if lang not in settings.LANGS:
            raise tornado.web.HTTPError(400)
        st = house.load_state()
        st["lang"] = lang
        house.save_state(st)
        house.set_ovos_lang(lang)
        speech.lang_changed()
        self.write({"ok": True})


class Speech(Base):
    """Speech on the devices or in the house (speech.py)."""
    def get(self):
        self.need_login()
        self.write({**speech.current(), **{"status": speech.status()}})

    def post(self):
        self.need_login()
        b = self.body()
        try:
            speech.choose(b.get("where"), b.get("model") or None, b.get("voice") or None)
        except ValueError:
            raise tornado.web.HTTPError(400)
        self.write({"ok": True})


def _bearer(handler):
    h = handler.request.headers.get("Authorization", "")
    return h[7:].strip() if h.lower().startswith("bearer ") else ""


class SpeechAuth(Base):
    """Caddy's forward_auth for /speech/: a paired Emkay (its HiveMind key as
    a Bearer token), or someone signed in to the house page."""
    def get(self):
        ok = speech.in_house() and (hive.has_key(_bearer(self)) or bool(self.https and self.current_user))
        self.set_status(200 if ok else 401)


def panel_url(host):
    return f"https://{host}:{settings.PANEL_PORT}/"


class HouseInfo(Base):
    """For a paired Emkay (Bearer: its HiveMind key): what the house offers
    it – speech (where, or none) and its control panel – asked when it
    connects, so phones paired earlier learn about it too."""
    def set_default_headers(self):
        super().set_default_headers()
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "Authorization")

    def options(self):
        self.set_status(204)

    def get(self):
        self.need_https()
        if not hive.has_key(_bearer(self)):
            raise tornado.web.HTTPError(401)
        host = self.request.host_name
        self.write({"speech": speech.for_emkay(host), "speech_state": speech.status()["state"],
                    "panel": panel_url(host)})


class Clients(Base):
    def get(self):
        self.need_login()
        self.write({"clients": hive.list_clients()})


class Remove(Base):
    def post(self):
        self.need_login()
        cid = str(self.body().get("id", ""))
        if not hive.delete_client(cid):
            raise tornado.web.HTTPError(404)
        ha.forget(cid)          # its device in Home Assistant goes too
        self.write({"ok": True})


def _house_base(handler):
    port = "" if settings.HTTPS_PORT == 443 else f":{settings.HTTPS_PORT}"
    return f"https://{handler.request.host_name}{port}"


class HomeAssistant(Base):
    """The house and its Emkays in Home Assistant (ha.py)."""
    def get(self):
        self.need_login()
        self.write(ha.status())

    def post(self):
        """{"url"} -> where the browser logs in to Home Assistant."""
        self.need_https()
        self.need_login()
        try:
            self.write({"go": ha.login_url(str(self.body().get("url", "")), _house_base(self))})
        except ValueError:
            raise tornado.web.HTTPError(400)


class HomeAssistantAuth(Base):
    """Home Assistant's login sends the browser back here with a code.

    The house's sign-in cookie is SameSite=Strict, so it doesn't come along
    on a navigation from Home Assistant; the state does the job instead: made
    for a signed-in browser by POST /api/ha, unguessable, used once, ten
    minutes. Then a page of the house's own moves on to the house page, so
    the cookie is sent there again."""
    async def get(self):
        self.need_https()
        try:
            await ha.finish_login(self.get_query_argument("code", ""), self.get_query_argument("state", ""),
                                  _house_base(self), f"https://{self.request.host_name}:{settings.PANEL_PORT}/")
            result = "ok"
        except ha.HAError as e:
            LOG.warning("Home Assistant login: %s", e)
            result = "failed"
        self.set_header("Content-Type", "text/html; charset=utf-8")
        self.set_header("Referrer-Policy", "no-referrer")     # the code is in this address
        self.write(f'<!doctype html><meta http-equiv="refresh" content="0;url=/?ha={result}">')


class HomeAssistantDisconnect(Base):
    async def post(self):
        self.need_login()
        await ha.disconnect()
        self.write({"ok": True})


def new_invite(name: str, host: str) -> dict:
    """A one-time code for "Add an Emkay", and the link a phone opens with it
    (http on the house's own name, so a phone that doesn't trust the house's
    certificate yet still gets there; pair.js goes on over https). Used by
    the house page and by the house's control panel (panelpage.py)."""
    _prune()
    name = str(name or "").strip()[:40] or "Emkay"
    code = secrets.token_urlsafe(18)
    INVITES[code] = {"name": name, "expires": time.time() + settings.INVITE_SECONDS, "paired": False}
    port = "" if settings.HTTP_PORT == 80 else f":{settings.HTTP_PORT}"
    return {"code": code, "url": f"http://{host}{port}/#t={code}", "seconds": settings.INVITE_SECONDS}


class Invite(Base):
    """A one-time code for "Add an Emkay", as a QR code."""
    def post(self):
        self.need_login()
        import segno
        inv = new_invite(self.body().get("name", ""), self.host)
        svg = segno.make(inv["url"], error="m").svg_inline(scale=8, border=2, dark="#05070a", light="#ffffff")
        self.write({**inv, "qr": svg})

    def get(self):
        """Whether the code has been used – the page closes the QR code then."""
        self.need_login()
        inv = INVITES.get(self.get_query_argument("code", ""))
        self.write({"paired": bool(inv and inv["paired"]), "expired": inv is None})


class Redeem(Base):
    """The phone trades its code for a client of its own and the pairing link."""
    def post(self):
        self.need_https()
        _prune()
        inv = INVITES.get(str(self.body().get("code", "")))
        if not inv or inv["paired"]:
            raise tornado.web.HTTPError(410)
        inv["paired"] = True
        key, password = hive.add_client(inv["name"])
        st = house.load_state()
        link = {
            "host": self.request.host_name,
            "port": settings.HTTPS_PORT,
            "path": settings.HIVEMIND_PATH,
            "ssl": True,
            "key": key,
            "password": password,
            "siteId": "".join(c if c.isalnum() else "-" for c in inv["name"].lower()).strip("-") or "emkay",
        }
        if st.get("lang"):
            link["lang"] = st["lang"]
        sp = speech.for_emkay(self.request.host_name)
        if sp:
            link["speech"] = sp
        link["panel"] = panel_url(self.request.host_name)
        b64 = base64.b64encode(json.dumps(link).encode()).decode()
        self.write({"url": f"{site.emkay_url(self.request.host_name)}#hivemind={tornado.escape.url_escape(b64, plus=False)}",
                    "name": inv["name"]})


class Emkay(Base):
    """Emkay served from the house: which build, and fetching a newer one."""
    def get(self):
        self.need_login()
        port = "" if settings.HTTPS_PORT == 443 else f":{settings.HTTPS_PORT}"
        self.write({**site.status(), "url": site.emkay_url(self.request.host_name),
                    "house_url": f"https://{self.request.host_name}{port}/emkay/"})

    def post(self):
        self.need_login()
        asyncio.get_running_loop().create_task(site.update(force=bool(self.body().get("force"))))
        self.write({"ok": True})


def make_app():
    return tornado.web.Application([
        (r"/", Root),
        (r"/pair", Pair),
        (r"/ping", Ping),
        (r"/tls-ask", TlsAsk),
        (r"/api/info", Info),
        (r"/api/setup", Setup),
        (r"/api/login", Login),
        (r"/api/logout", Logout),
        (r"/api/lang", Lang),
        (r"/api/clients", Clients),
        (r"/api/clients/remove", Remove),
        (r"/api/invite", Invite),
        (r"/api/redeem", Redeem),
        (r"/api/emkay", Emkay),
        (r"/api/panel-auth", PanelAuth),
        (r"/api/speech", Speech),
        (r"/api/speech-auth", SpeechAuth),
        (r"/api/house-info", HouseInfo),
        (r"/api/ha", HomeAssistant),
        (r"/api/ha/disconnect", HomeAssistantDisconnect),
        (r"/ha-auth", HomeAssistantAuth),
        (r"/static/texts\.json", Texts),
        (r"/static/(.*)", tornado.web.StaticFileHandler, {"path": str(WEB)}),
    ], xheaders=False)
