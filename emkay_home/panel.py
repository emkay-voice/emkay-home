"""The OpenVoiceOS control panel of the house, behind Emkay Home's sign-in.

The emkay_home_panel container runs the stock ovos-control-panel on
localhost; Caddy serves it at https://<house>:PANEL_PORT/ and asks this page
first (forward_auth, /api/panel-auth) whether the browser is signed in to
Emkay Home. If it is, the answer carries the panel's own token as an
Authorization header, which Caddy passes on to the panel – so there is one
password for the whole house, and the panel's token is never shown to
anyone. If it isn't, the browser goes to the house page to sign in and comes
back.

The token lives where the panel reads it, in the user layer of mycroft.conf
(webui.access_token): made here once, read here every time, so a token
changed in the panel itself keeps working.
"""
import json
import logging
import secrets
import socket

from . import settings

LOG = logging.getLogger("emkay-home")


def _conf_path():
    return settings.OVOS_CONFIG / "mycroft.conf"


def _load():
    try:
        return json.loads(_conf_path().read_text())
    except (OSError, ValueError):
        return {}


def prepare():
    """A token for the panel, and the names the house may be opened by (the
    panel refuses other Host names; numeric addresses always pass)."""
    conf = _load()
    webui = conf.setdefault("webui", {})
    changed = False
    if not webui.get("access_token"):
        webui["access_token"] = secrets.token_urlsafe(32)
        changed = True
    names = set(webui.get("hostnames") or [])
    want = {f"{socket.gethostname()}.local", *settings.EXTRA_NAMES}
    if not want <= names:
        webui["hostnames"] = sorted(names | want)
        changed = True
    if changed:
        try:
            _conf_path().parent.mkdir(parents=True, exist_ok=True)
            _conf_path().write_text(json.dumps(conf, indent=2))
            LOG.info("the control panel's token and names are in mycroft.conf")
        except OSError as e:
            LOG.warning("could not prepare the control panel: %s", e)


def token():
    return (_load().get("webui") or {}).get("access_token") or ""
