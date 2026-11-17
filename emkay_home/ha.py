"""Home Assistant: the house and its Emkays as devices there.

"Connect to my Home Assistant" on the house page: the browser goes to Home
Assistant's own login (IndieAuth, with the house's address as the app), comes
back to /ha-auth with a code, and the house trades it for a long-lived token
of its own. Nobody types a token, and Home Assistant's password is never
seen here.

Then ovos-phal-plugin-ha-link runs in this process, on the house's bus: the
house becomes a device in Home Assistant (accepted once, under Discovered),
with its control panel; every Emkay paired with the house becomes its own
device there too, connected via the house, with its own volume, listening
on/off and "say" (andlo/ha-ovos-integration#12). And
ovos-assist-pipeline-plugin hands Home Assistant's Assist what it knows
("turn off the light on the stairs").

Kept in DATA/ha.json (only readable here): Home Assistant's address, the
token, and the house's device id there.
"""
import asyncio
import json
import logging
import secrets
import time
import urllib.parse
import uuid

import tornado.httpclient
import tornado.websocket

from . import house, panel, settings

LOG = logging.getLogger("emkay-home")
STATE = settings.DATA / "ha.json"
ASSIST = "ovos-assist-pipeline-plugin"
#: login attempts underway: state -> (Home Assistant's address, expiry)
_PENDING: dict[str, tuple[str, float]] = {}
_link = {"plugin": None, "bus": None, "state": "off"}


class HAError(Exception):
    """Home Assistant could not be reached, or refused."""


def load() -> dict:
    try:
        return json.loads(STATE.read_text())
    except (OSError, ValueError):
        return {}


def _save(data: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(data, indent=2))
    STATE.chmod(0o600)


def status() -> dict:
    st = load()
    return {"url": st.get("url"), "connected": bool(st.get("token")), "state": _link["state"]}


def _clean_url(url: str) -> str:
    url = (url or "").strip().rstrip("/")
    if url and "://" not in url:
        url = "http://" + url
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def login_url(ha_url: str, house_base: str) -> str:
    """Where the browser logs in to Home Assistant; it comes back to /ha-auth."""
    ha_url = _clean_url(ha_url)
    now = time.time()
    for s, (_, exp) in list(_PENDING.items()):
        if exp < now:
            _PENDING.pop(s, None)
    state = secrets.token_urlsafe(16)
    _PENDING[state] = (ha_url, now + 600)
    q = urllib.parse.urlencode({"response_type": "code", "client_id": f"{house_base}/",
                                "redirect_uri": f"{house_base}/ha-auth", "state": state})
    return f"{ha_url}/auth/authorize?{q}"


async def finish_login(code: str, state: str, house_base: str, panel_url: str) -> None:
    """The code from Home Assistant's login -> a long-lived token for the house."""
    ha_url, _ = _PENDING.pop(state, (None, 0))
    if not ha_url or not code:
        raise HAError("expired")
    http = tornado.httpclient.AsyncHTTPClient()
    try:
        r = await http.fetch(f"{ha_url}/auth/token", method="POST", request_timeout=15, body=urllib.parse.urlencode({
            "grant_type": "authorization_code", "code": code, "client_id": f"{house_base}/"}))
        tokens = json.loads(r.body)
        ws = await tornado.websocket.websocket_connect(
            ha_url.replace("http", "ws", 1) + "/api/websocket", connect_timeout=15)
        await ws.read_message()
        ws.write_message(json.dumps({"type": "auth", "access_token": tokens["access_token"]}))
        if json.loads(await ws.read_message()).get("type") != "auth_ok":
            raise HAError("refused")
        ws.write_message(json.dumps({"id": 1, "type": "auth/long_lived_access_token",
                                     "client_name": "Emkay Home", "lifespan": 3650}))
        answer = json.loads(await ws.read_message())
        ws.close()
        if not answer.get("success"):
            raise HAError("refused")
        # the login's own refresh token isn't needed any more
        await http.fetch(f"{ha_url}/auth/revoke", method="POST", raise_error=False, request_timeout=10,
                         body=urllib.parse.urlencode({"token": tokens.get("refresh_token", "")}))
    except (OSError, tornado.httpclient.HTTPClientError, ValueError, KeyError) as e:
        raise HAError(f"unreachable: {e}") from e
    st = load()
    _save({**st, "url": ha_url, "token": answer["result"], "panel_url": panel_url,
           "device_id": st.get("device_id") or f"emkay-home-{uuid.uuid4()}"})
    ensure_assist()
    await start()


def ensure_assist() -> None:
    """ovos-assist-pipeline-plugin in the house's OVOS: installed (skills.list)
    and in the intent pipeline after adapt high, as in Emkay. ovos_core is
    restarted if anything changed."""
    changed = False
    lst = settings.OVOS_CONFIG / "skills.list"
    try:
        lines = lst.read_text().splitlines() if lst.exists() else []
        if ASSIST not in (line.strip() for line in lines):
            lst.write_text("\n".join([*lines, ASSIST]) + "\n")
            changed = True
        path = settings.OVOS_CONFIG / "mycroft.conf"
        conf = json.loads(path.read_text()) if path.exists() else {}
        pipeline = (conf.get("intents") or {}).get("pipeline")
        if pipeline and ASSIST not in pipeline:
            at = pipeline.index("ovos-adapt-pipeline-plugin-high") + 1 \
                if "ovos-adapt-pipeline-plugin-high" in pipeline else len(pipeline)
            pipeline.insert(at, ASSIST)
            path.write_text(json.dumps(conf, indent=2))
            changed = True
    except (OSError, ValueError) as e:
        LOG.warning("could not add Home Assistant's Assist to the house's OVOS: %s", e)
    if changed:
        house.restart_ovos()


def _start_now(st: dict) -> None:
    from ovos_bus_client import MessageBusClient
    from ovos_phal_plugin_ha_link import HALinkPlugin
    bus = MessageBusClient(host="127.0.0.1", port=8181)
    bus.run_in_thread()
    bus.connected_event.wait(30)
    config = {"url": st["url"], "token": st["token"], "device_id": st["device_id"],
              "name": "Emkay Home", "model": "Emkay Home",
              "panel_url": "http://127.0.0.1:8599", "panel_token": panel.token()}
    if st.get("panel_url"):     # "Open control panel" on the house's page in HA
        config["panel_public_url"] = st["panel_url"]
    plugin = HALinkPlugin(bus=bus, config=config)
    link_event = plugin.link.on_event

    def on_event(event):
        kind = event.get("type")
        if kind in ("pending", "ready", "lost", "removed", "displaced"):
            _link["state"] = kind
        link_event(event)

    plugin.link.on_event = on_event
    _link.update(plugin=plugin, bus=bus, state="connecting")


async def start() -> None:
    """The link, if the house is connected to Home Assistant."""
    st = load()
    if not st.get("token") or _link["plugin"] is not None:
        return
    try:
        await asyncio.get_running_loop().run_in_executor(None, _start_now, st)
        LOG.info("linked to Home Assistant at %s", st["url"])
    except Exception as e:  # noqa: BLE001 - the house runs without it
        _link["state"] = "error"
        LOG.warning("could not link to Home Assistant: %s", e)


async def disconnect() -> None:
    """Stop the link and give the token back to Home Assistant. The devices
    stay in Home Assistant until someone deletes them there."""
    plugin, bus = _link["plugin"], _link["bus"]
    if plugin is not None:
        plugin.shutdown()
    if bus is not None:
        bus.close()
    _link.update(plugin=None, bus=None, state="off")
    st = load()
    if st.get("token"):
        try:
            await _revoke(st["url"], st["token"])
        except Exception as e:  # noqa: BLE001 - it is forgotten here either way
            LOG.info("could not revoke the house's token in Home Assistant: %s", e)
    st.pop("token", None)
    _save(st)


async def _revoke(ha_url: str, token: str) -> None:
    """The long-lived token is a refresh token in HA; delete the one we use."""
    ws = await tornado.websocket.websocket_connect(
        ha_url.replace("http", "ws", 1) + "/api/websocket", connect_timeout=10)
    try:
        await ws.read_message()
        ws.write_message(json.dumps({"type": "auth", "access_token": token}))
        if json.loads(await ws.read_message()).get("type") != "auth_ok":
            return
        ws.write_message(json.dumps({"id": 1, "type": "auth/refresh_tokens"}))
        tokens = json.loads(await ws.read_message()).get("result") or []
        mine = next((t for t in tokens if t.get("is_current")), None)
        if mine:
            ws.write_message(json.dumps({"id": 2, "type": "auth/delete_refresh_token",
                                         "refresh_token_id": mine["id"]}))
            await ws.read_message()
    finally:
        ws.close()


def forget(client_id: str) -> None:
    """An Emkay was removed from the house: its device goes from Home Assistant."""
    bus = _link["bus"]
    if bus is not None:
        from ovos_bus_client.message import Message
        bus.emit(Message("ovos.ha_link.satellite.forget", {"id": client_id}))
