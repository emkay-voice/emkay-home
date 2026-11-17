"""Emkay itself, served from the house (emkay-voice/emkay#30).

Emkay is a static site. Every deploy of app.emkay.ai is also published as
one download, the release "site" of emkay-voice/emkay: emkay-site.tar.gz,
its .sha256, and emkay-site.json (the site's build.json). The house fetches
it on the first start and then once a day if there is a newer build, and
Caddy serves it at https://<house>/emkay/ – so a phone paired with the house
loads Emkay from the house too, not from the internet.

On disk (the emkay_site volume, read-only for Caddy):

    /emkay-site/current -> 3f2a9c1-412      what Caddy serves
    /emkay-site/3f2a9c1-412/index.html …    one build (commit-build)

A new build is unpacked next to the old one and `current` is switched in one
step, so Caddy never serves half a site.
"""
import asyncio
import hashlib
import json
import logging
import os
import shutil
import tarfile
import time
import urllib.request
from pathlib import Path

from . import settings

LOG = logging.getLogger("emkay-home")

STATUS = {"state": "idle", "progress": None, "error": None, "checked": None}
_lock = asyncio.Lock()


def installed():
    """The build.json of the Emkay the house serves, or None."""
    try:
        return json.loads((settings.SITE_DIR / "current" / "build.json").read_text())
    except (OSError, ValueError):
        return None


def serving_from_house():
    return settings.EMKAY_URL in ("", "house") and installed() is not None


def emkay_url(host):
    """Where a paired phone opens Emkay."""
    if serving_from_house():
        port = "" if settings.HTTPS_PORT == 443 else f":{settings.HTTPS_PORT}"
        return f"https://{host}{port}/emkay/"
    return settings.EMKAY_URL if settings.EMKAY_URL not in ("", "house") else "https://app.emkay.ai/"


def _get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "emkay-home"})
    return urllib.request.urlopen(req, timeout=timeout)


def _name(build):
    return f"{str(build.get('commit', 'unknown'))[:12]}-{build.get('build', 'local')}"


def _update_blocking(force=False):
    base = settings.SITE_URL.rstrip("/") + "/"
    with _get(base + "emkay-site.json") as r:
        remote = json.loads(r.read())
    STATUS["checked"] = time.time()
    local = installed()
    if local and not force and _name(local) == _name(remote):
        LOG.info("Emkay %s is the newest", _name(local))
        return False

    with _get(base + "emkay-site.tar.gz.sha256") as r:
        want = r.read().decode().split()[0].lower()

    root = settings.SITE_DIR
    root.mkdir(parents=True, exist_ok=True)
    tmp = root / ".download.tar.gz"
    LOG.info("downloading Emkay %s", _name(remote))
    STATUS.update(state="downloading", progress=0)
    h = hashlib.sha256()
    with _get(base + "emkay-site.tar.gz", timeout=60) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while chunk := r.read(1 << 20):
            f.write(chunk)
            h.update(chunk)
            done += len(chunk)
            STATUS["progress"] = round(done / total, 3) if total else None
    if h.hexdigest() != want:
        tmp.unlink(missing_ok=True)
        raise RuntimeError("the download doesn't match its checksum")

    STATUS.update(state="unpacking", progress=None)
    name = _name(remote)
    work = root / f".{name}.tmp"
    shutil.rmtree(work, ignore_errors=True)
    with tarfile.open(tmp) as t:
        t.extractall(work, filter="data")
    tmp.unlink(missing_ok=True)
    if not (work / "index.html").exists():
        shutil.rmtree(work, ignore_errors=True)
        raise RuntimeError("the download has no index.html")
    dest = root / name
    shutil.rmtree(dest, ignore_errors=True)
    work.rename(dest)

    # switch in one step, then tidy up the old builds
    link = root / ".current.tmp"
    link.unlink(missing_ok=True)
    link.symlink_to(name)
    os.replace(link, root / "current")
    for old in root.iterdir():
        if old.is_dir() and not old.is_symlink() and old.name not in (name,) and not old.name.startswith("."):
            shutil.rmtree(old, ignore_errors=True)
    LOG.info("Emkay %s is served from the house", name)
    return True


async def update(force=False):
    """Fetch the newest Emkay if it is newer than the one the house has."""
    if _lock.locked():
        return
    async with _lock:
        STATUS.update(state="checking", progress=None, error=None)
        try:
            await asyncio.to_thread(_update_blocking, force)
            STATUS.update(state="idle", progress=None)
        except Exception as e:   # the house works without it (app.emkay.ai)
            LOG.warning("could not update Emkay: %s", e)
            STATUS.update(state="error", progress=None, error=str(e))


async def keep_updated():
    """On the first start, then once a day."""
    if settings.EMKAY_URL not in ("", "house"):
        return
    while True:
        await update()
        await asyncio.sleep(settings.SITE_CHECK_HOURS * 3600)


def status():
    b = installed()
    return {
        "mode": "house" if settings.EMKAY_URL in ("", "house") else "url",
        "serving": serving_from_house(),
        "installed": {k: b.get(k) for k in ("version", "build", "commit", "built")} if b else None,
        **STATUS,
    }
