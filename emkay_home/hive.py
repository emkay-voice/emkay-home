"""hivemind-core: its clients (the paired Emkays), and keeping it running.

The clients are hivemind-core's own database (ClientDatabase), used the
way `hivemind-core add-client` / `delete-client` use it, so a house set up
here can still be looked after with the stock CLI. A running hivemind-core
sees a new or removed client at the next connection – no restart needed.
"""
import asyncio
import copy
import hashlib
import json
import logging
import secrets
import sys
from pathlib import Path

from . import settings

LOG = logging.getLogger("emkay-home")


def _db():
    # imported late: hivemind-core logs on import, and the page should start
    # (and tests run) even where it is not installed
    from hivemind_core.database import ClientDatabase
    return ClientDatabase()


def client_id(api_key: str) -> str:
    """A handle for a client that is not its secret access key."""
    return hashlib.sha256(api_key.encode()).hexdigest()[:16]


def _live(c):
    # a deleted client stays in the JSON database as api_key "revoked"
    return c.api_key and c.api_key != "revoked" and c.client_id != -1


def list_clients():
    with _db() as db:
        return [{"id": client_id(c.api_key), "name": c.name,
                 "last_seen": c.last_seen if c.last_seen and c.last_seen > 0 else None}
                for c in db if _live(c)]


def add_client(name: str):
    """A new client; returns (access key, password).

    The key is 36 hex characters: Emkay sends "Emkay:<key>" base64-encoded in
    the address, and with 42 characters that base64 needs no "=" padding –
    hivemind-websocket-protocol does not URL-decode it (%3D), and a padded one
    is refused.
    """
    key = secrets.token_hex(18)
    password = secrets.token_urlsafe(24)
    with _db() as db:
        if not db.add_client(name, key, password=password):
            raise RuntimeError("hivemind-core could not add the client")
    return key, password


def delete_client(cid: str) -> bool:
    with _db() as db:
        for c in db:
            if _live(c) and client_id(c.api_key) == cid:
                return bool(db.delete_client(c.api_key))
    return False


def write_server_config():
    """hivemind-core listens on localhost only – the house reaches it through
    Caddy at /hivemind, over https. Written once; edit it freely afterwards."""
    from ovos_utils.xdg_utils import xdg_config_home
    path = Path(xdg_config_home()) / "hivemind-core" / "server.json"
    if path.exists():
        return
    try:
        # hivemind-core's own defaults (it only fills in missing top-level keys)
        from hivemind_core.config import _DEFAULT
        conf = copy.deepcopy(_DEFAULT)
    except ImportError:
        conf = {}
    ws = dict(conf.get("network_protocol", {}).get("hivemind-websocket-plugin", {}))
    ws.update({"host": "127.0.0.1", "port": settings.HIVEMIND_PORT, "ssl": False})
    # only the websocket, and only on localhost: Caddy is the way in
    conf["network_protocol"] = {"hivemind-websocket-plugin": ws}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(conf, indent=2))
    LOG.info("wrote %s", path)


def _hivemind_core():
    # next to this Python (the image's venv, or a venv not on PATH), else PATH
    here = Path(sys.executable).parent / "hivemind-core"
    return str(here) if here.exists() else "hivemind-core"


async def keep_running(argv=None):
    """Run hivemind-core and start it again if it stops."""
    argv = argv or (_hivemind_core(), "listen")
    delay = 2
    while True:
        LOG.info("starting %s", " ".join(argv))
        try:
            proc = await asyncio.create_subprocess_exec(*argv)
            started = asyncio.get_running_loop().time()
            code = await proc.wait()
        except FileNotFoundError:
            LOG.error("%s is not installed; pairing works, but nobody answers", argv[0])
            return
        ran = asyncio.get_running_loop().time() - started
        delay = 2 if ran > 60 else min(delay * 2, 60)
        LOG.warning("%s stopped (%s); again in %ss", argv[0], code, delay)
        await asyncio.sleep(delay)
