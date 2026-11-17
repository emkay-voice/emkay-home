"""The stock ovos-control-panel with Emkay's look.

Runs `ovos-control-panel` exactly as its own console entry point does, with
one thing added on the way out: every HTML page gets Emkay's colours in a
<style> before </head> – the same tokens Emkay puts on the panel in the
browser (web/sw.js in emkay-voice/emkay, THEME), so the panel looks the
same on the phone and in the house. Only the values of the panel's own
colour tokens change; its pages, routes and CSS are untouched, and its
Content-Security-Policy already allows inline styles.

When Emkay's theme changes, change THEME here too.
"""
import ovos_webui.service as service

#: Emkay's dark palette and blue accent, as on the phone. "html:root:not(
#: [data-emkay])" outranks the panel's dark-mode rules, so it holds in every
#: mode. The pages for hardware the house doesn't have (Wi-Fi – the host
#: looks after that –, the Mark 1 faceplate, desktop apps) and the wake word
#: test (the house has no microphone; the Emkays are its ears) are left out
#: of the menu; they still open if asked for.
THEME = b"""<style id="emkay-theme">
html:root:not([data-emkay]) {
  color-scheme: dark;
  --bg: #05070a; --bg-soft: #000000; --card: #141b24; --card-soft: #1d232b;
  --bevel: rgba(255, 255, 255, 0.05); --ink: #ffffff; --muted: #8a96a8; --line: #232c38;
  --accent: #22a7f0; --accent-strong: #1478c8; --accent-hover: #0f6ab3;
  --accent-ink: #ffffff; --accent-wash: rgba(34, 167, 240, 0.15);
  --ok: #3ddc84; --warn: #ffc93c; --bad: #ff5c5c;
  --shadow: 0 1px 2px rgba(0, 0, 0, 0.5), 0 12px 34px rgba(0, 0, 0, 0.45);
  --radius: 16px;
}
nav a[href$="/network"], nav a[href$="/mark1"],
nav a[href$="/apps"] { display: none !important; }
main h2:has(+ .card #wake-test), main .card:has(#wake-test) { display: none !important; }
</style>"""


class EmkayTheme:
    """ASGI middleware: THEME into text/html responses, nothing else."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        start, chunks = None, []

        async def wrapped(message):
            nonlocal start
            if message["type"] == "http.response.start":
                headers = dict(message.get("headers") or [])
                if b"text/html" in headers.get(b"content-type", b""):
                    start = message          # held until the whole page is here
                    return
                return await send(message)
            if message["type"] == "http.response.body" and start is not None:
                chunks.append(message.get("body", b""))
                if message.get("more_body"):
                    return
                body = b"".join(chunks)
                i = body.lower().rfind(b"</head>")
                if i >= 0:
                    body = body[:i] + THEME + body[i:]
                headers = [(k, v) for k, v in start.get("headers") or []
                           if k.lower() != b"content-length"]
                headers.append((b"content-length", str(len(body)).encode()))
                await send({**start, "headers": headers})
                return await send({"type": "http.response.body", "body": body})
            return await send(message)

        return await self.app(scope, receive, wrapped)


_create_app = service.create_app


def create_app(*args, **kwargs):
    return EmkayTheme(_create_app(*args, **kwargs))


service.create_app = create_app

if __name__ == "__main__":
    service.main()
