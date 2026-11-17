#!/usr/bin/env python3
"""Make emkay_home/profile/skills.list from Emkay's own requirements.

The house runs the same skills as Emkay in the browser (app.emkay.ai), so
the two stay alike: this reads Emkay's requirements/browser.txt (from a
checkout, or from GitHub at a ref) and keeps the skills, media providers
and pipeline plugins. What ovos_core already has (ovos-core[plugins]), the
browser's own parts (GUI, audio, speech servers) and the skills that only
make sense in a browser are left out.

    python tools/sync_profile.py                    # emkay-voice/emkay, main
    python tools/sync_profile.py --ref v0.3.0
    python tools/sync_profile.py --file ../emkay/requirements/browser.txt
"""
import argparse
import re
import sys
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "emkay_home" / "profile" / "skills.list"
RAW = "https://raw.githubusercontent.com/emkay-voice/emkay/{ref}/requirements/browser.txt"

#: what the house keeps from Emkay's list
KEEP = re.compile(r"^(ovos-core\[skills|ovos-skill-|ovos-media-provider-|ovos-common-[a-z-]+-pipeline-plugin)")
#: browser-only: the page does what these ask for (full screen, the
#: network log of the browser) – a house has no page of its own
BROWSER_ONLY = {"ovos-skill-kiosk", "ovos-skill-guardian"}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ref", default="main")
    p.add_argument("--file")
    a = p.parse_args()
    if a.file:
        text, source = Path(a.file).read_text(), a.file
    else:
        source = RAW.format(ref=a.ref)
        text = urllib.request.urlopen(source, timeout=30).read().decode()

    keep = []
    for line in text.splitlines():
        req = line.split("#", 1)[0].strip()
        name = re.split(r"[<>=!~\[ ;]", req, maxsplit=1)[0]
        if req and KEEP.match(req) and name not in BROWSER_ONLY:
            keep.append(req)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        "# Emkay's skills, for the house (ovos_core installs these at start).\n"
        f"# Made by tools/sync_profile.py from {source.replace('https://raw.githubusercontent.com/', '')}\n"
        "# – edit Emkay's list, not this one. Left out here: "
        + ", ".join(sorted(BROWSER_ONLY)) + " (browser-only).\n"
        + "\n".join(keep) + "\n")
    print(f"{OUT}: {len(keep)} lines", file=sys.stderr)


if __name__ == "__main__":
    main()
