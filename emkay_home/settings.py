"""Where things are, from the environment (set in compose/docker-compose.yml)."""
import os
from pathlib import Path


def _int(name, default):
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


#: Emkay Home's own state: the house password and the chosen language.
DATA = Path(os.environ.get("EMKAY_HOME_DATA", "/data"))
#: The OVOS user config (~/.config/mycroft of the ovos_core container).
OVOS_CONFIG = Path(os.environ.get("EMKAY_HOME_OVOS_CONFIG", "/ovos-config"))
#: Where the page listens; only Caddy talks to it.
LISTEN_HOST = os.environ.get("EMKAY_HOME_LISTEN", "127.0.0.1")
LISTEN_PORT = _int("EMKAY_HOME_PORT", 8099)

#: The ports Caddy serves the house on (the QR code and the pairing link use them).
HTTP_PORT = _int("HTTP_PORT", 80)
HTTPS_PORT = _int("HTTPS_PORT", 443)

#: The root of the house's own CA ("tls internal"), as Caddy serves it.
CA_URL = os.environ.get("EMKAY_HOME_CA_URL", f"http://127.0.0.1:{HTTP_PORT}/ca.crt")

#: hivemind-core, behind Caddy at /hivemind.
HIVEMIND_PORT = _int("HIVEMIND_PORT", 5678)
HIVEMIND_PATH = "/hivemind"

#: The Emkay a paired phone opens. app.emkay.ai until Emkay is served from
#: the house too (emkay-voice/emkay#30).
EMKAY_URL = os.environ.get("EMKAY_URL", "https://app.emkay.ai/")

#: Extra names the house may get a certificate for, besides LAN addresses,
#: *.local, *.lan, *.home.arpa, *.internal and names without a dot.
EXTRA_NAMES = {n.strip().lower() for n in os.environ.get("EMKAY_HOME_NAMES", "").split(",") if n.strip()}

#: How long a QR code works.
INVITE_SECONDS = _int("EMKAY_HOME_INVITE_SECONDS", 600)

#: Emkay's languages (OVOS languages with ≥80 % translation), as Emkay has them.
LANGS = {
    "en-us": "English (US)", "en-gb": "English (UK)", "da-dk": "Dansk",
    "de-de": "Deutsch", "es-es": "Español", "fr-fr": "Français",
    "it-it": "Italiano", "nl-nl": "Nederlands", "pt-pt": "Português",
    "pt-br": "Português (Brasil)", "ca-es": "Català", "eu-es": "Euskara",
}
