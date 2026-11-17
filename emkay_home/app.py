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

from . import hive, house, panel, settings, site

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
                        "connect-src 'self' https:; frame-ancestors 'none'")
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
        self.redirect(f"https://{self.request.host_name}{port}/?next=panel")


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
        self.write({"ok": True})


class Clients(Base):
    def get(self):
        self.need_login()
        self.write({"clients": hive.list_clients()})


class Remove(Base):
    def post(self):
        self.need_login()
        if not hive.delete_client(str(self.body().get("id", ""))):
            raise tornado.web.HTTPError(404)
        self.write({"ok": True})


class Invite(Base):
    """A one-time code for "Add an Emkay", as a QR code."""
    def post(self):
        self.need_login()
        import segno
        _prune()
        name = str(self.body().get("name", "")).strip()[:40] or "Emkay"
        code = secrets.token_urlsafe(18)
        INVITES[code] = {"name": name, "expires": time.time() + settings.INVITE_SECONDS, "paired": False}
        port = "" if settings.HTTP_PORT == 80 else f":{settings.HTTP_PORT}"
        url = f"http://{self.host}{port}/#t={code}"
        svg = segno.make(url, error="m").svg_inline(scale=8, border=2, dark="#05070a", light="#ffffff")
        self.write({"code": code, "url": url, "qr": svg, "seconds": settings.INVITE_SECONDS})

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
        (r"/static/texts\.json", Texts),
        (r"/static/(.*)", tornado.web.StaticFileHandler, {"path": str(WEB)}),
    ], xheaders=False)
