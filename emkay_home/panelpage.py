"""The Emkays in the house, as a page of the house's control panel.

The panel draws the page from emkay_home's controlpanel.json and asks over
OpenVoiceOS' message bus; this answers, with the same code the house page
uses (hive.py, app.new_invite). Each message starts with BUS, the page's own
prefix:

    ovos.emkay_home.devices          -> {"items": [{"id", "name", "status", "last_seen"}]}
    ovos.emkay_home.pair   {"host"}  -> {"url", "seconds", "minutes"}   (drawn as a QR code)
    ovos.emkay_home.device.rename {"id", "name"}
    ovos.emkay_home.device.remove {"id"}

The panel asks for "pair" only with its access token, and the link is only
ever drawn as a QR code there, never shown as text. A failure answers
{"error": ...}, which the panel shows.
"""
import logging
import threading

from . import hive, house, settings

LOG = logging.getLogger("emkay-home")

BUS = "ovos.emkay_home."


def devices() -> dict:
    items = []
    for c in hive.list_clients():
        items.append({"id": c["id"], "name": c["name"],
                      "status": "seen" if c.get("last_seen") else "never",
                      "last_seen": c.get("last_seen")})
    return {"items": sorted(items, key=lambda c: c["name"].lower())}


def pair(host: str) -> dict:
    from .app import new_invite
    host = (host or "").strip()
    if not host or house.is_loopback(host):
        host = house.lan_ip()
    inv = new_invite("", host)
    return {"url": inv["url"], "seconds": inv["seconds"], "minutes": max(1, inv["seconds"] // 60)}


def rename(cid: str, name: str) -> dict:
    name = str(name or "").strip()[:40]
    if not name:
        return {"error": "emkay-home.err.name"}
    if not hive.rename_client(cid, name):
        return {"error": "emkay-home.err.gone"}
    return {"ok": True}


def remove(cid: str) -> dict:
    return {"ok": True} if hive.delete_client(str(cid or "")) else {"error": "emkay-home.err.gone"}


def _answer(bus, message, work):
    try:
        out = work()
    except Exception as e:  # noqa: BLE001 - the page says it went wrong
        LOG.warning("control panel page: %s failed: %s", message.msg_type, e)
        out = {"error": "emkay-home.err.failed"}
    bus.emit(message.response(out))


def attach(bus) -> None:
    """Answer the page's messages on ``bus``."""
    on = bus.on
    on(BUS + "devices", lambda m: _answer(bus, m, devices))
    on(BUS + "pair", lambda m: _answer(bus, m, lambda: pair(m.data.get("host", ""))))
    on(BUS + "device.rename", lambda m: _answer(bus, m, lambda: rename(m.data.get("id"), m.data.get("name"))))
    on(BUS + "device.remove", lambda m: _answer(bus, m, lambda: remove(m.data.get("id"))))


def start() -> None:
    """Connect to the house's OpenVoiceOS bus and answer the page, in a thread
    of its own; the house runs on without it (the page then says nobody
    answered)."""
    def run():
        try:
            from ovos_bus_client import MessageBusClient
            bus = MessageBusClient(host=settings.BUS_HOST, port=settings.BUS_PORT)
            attach(bus)
            bus.run_in_thread()
            if bus.connected_event.wait(60):
                LOG.info("the control panel's Emkays page answers on the bus")
        except Exception as e:  # noqa: BLE001
            LOG.warning("the control panel's Emkays page is not answered: %s", e)
    threading.Thread(target=run, name="panel-page", daemon=True).start()
