"""The house: Emkay Home's own state, the OVOS profile, addresses and the CA."""
import hashlib
import ipaddress
import json
import logging
import secrets
import shutil
import socket
import urllib.request
from pathlib import Path

from . import settings

LOG = logging.getLogger("emkay-home")
PROFILE = Path(__file__).parent / "profile"


# --- Emkay Home's own state -------------------------------------------------

def _state_path():
    return settings.DATA / "emkay-home.json"


def load_state():
    try:
        return json.loads(_state_path().read_text())
    except (OSError, ValueError):
        return {}


def save_state(state):
    p = _state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.chmod(0o600)
    tmp.replace(p)


def set_password(state, password):
    salt = secrets.token_bytes(16)
    state["password"] = {"salt": salt.hex(), "iterations": 300_000,
                         "hash": hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 300_000).hex()}


def check_password(state, password):
    p = state.get("password")
    if not p:
        return False
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(p["salt"]), p["iterations"]).hex()
    return secrets.compare_digest(h, p["hash"])


# --- OVOS ---------------------------------------------------------------------

def seed_ovos_profile():
    """Emkay's OVOS profile (mycroft.conf, skills.list) into the OVOS config,
    the first time only – after that they are the house's to change."""
    settings.OVOS_CONFIG.mkdir(parents=True, exist_ok=True)
    for name in ("mycroft.conf", "skills.list"):
        dst = settings.OVOS_CONFIG / name
        if not dst.exists() and (PROFILE / name).exists():
            shutil.copy(PROFILE / name, dst)
            LOG.info("seeded %s", dst)


def restart_ovos():
    """Ask for ovos_core to be restarted (it loads a new language's skills
    only when it starts). The restarter container does it: it alone has
    Docker, and it can do nothing but restart ovos_core."""
    try:
        settings.REQUESTS.mkdir(parents=True, exist_ok=True)
        (settings.REQUESTS / "restart-ovos_core").touch()
        LOG.info("asked for ovos_core to be restarted")
    except OSError as e:
        LOG.warning("could not ask for ovos_core to be restarted: %s", e)


def set_ovos_lang(lang):
    """The house's language, in the OVOS user config (mycroft.conf)."""
    path = settings.OVOS_CONFIG / "mycroft.conf"
    try:
        conf = json.loads(path.read_text())
    except (OSError, ValueError):
        conf = {}
    changed = conf.get("lang") != lang
    conf["lang"] = lang
    path.write_text(json.dumps(conf, indent=2))
    if changed:
        restart_ovos()


# --- addresses ----------------------------------------------------------------

def lan_ip():
    """This machine's address on the LAN (nothing is sent)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.0.2.1", 9))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def is_loopback(host):
    if host in ("localhost", "localhost.localdomain"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def may_have_certificate(name):
    """Whether Caddy may make a certificate for this name (its on-demand "ask"):
    the house's own addresses and names, never a public one."""
    name = (name or "").strip().lower().rstrip(".")
    if not name:
        return False
    try:
        ip = ipaddress.ip_address(name.strip("[]"))
        return ip.is_private or ip.is_loopback or ip.is_link_local
    except ValueError:
        pass
    if name in settings.EXTRA_NAMES:
        return True
    if "." not in name:
        return True
    return name.endswith((".local", ".lan", ".home.arpa", ".internal", ".home"))


# --- the house's certificate authority ----------------------------------------

_ca_cache = None


def ca_pem():
    """The house's root certificate, as Caddy serves it at /ca.crt. emkay-home
    never sees Caddy's storage (where the CA's key is)."""
    global _ca_cache
    if _ca_cache is None:
        try:
            with urllib.request.urlopen(settings.CA_URL, timeout=3) as r:
                pem = r.read()
            if pem.startswith(b"-----BEGIN CERTIFICATE-----"):
                _ca_cache = pem
        except OSError:
            pass
    return _ca_cache


def ca_fingerprint(pem):
    """SHA-256 fingerprint as phones show it (AA:BB:…), to compare by eye."""
    import base64
    body = b"".join(l for l in pem.splitlines() if l and not l.startswith(b"-----"))
    der = base64.b64decode(body)
    return ":".join(f"{b:02X}" for b in hashlib.sha256(der).digest())
