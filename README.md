# Emkay Home

**The OpenVoiceOS for the house** – the one your Emkays – phones, tablets, PCs and TVs with
[Emkay](https://emkay.ai) – are satellites of. As easy as Emkay itself: open
the page, tap here and there, and you're up.

> **Status: early alpha.** Docker compose with OVOS, hivemind-core and the
> house page; "Add an Emkay" with a QR code; the house's own certificate;
> Emkay itself served from the house; speech in the house; the one-line
> install script; in all of Emkay's languages. The Home Assistant add-on
> comes next (see [Roadmap](#roadmap)).
> Background and decisions: [emkay-voice/emkay#33](https://github.com/emkay-voice/emkay/issues/33).

## What it is

Emkay runs OpenVoiceOS in the browser of a device – a phone, tablet, PC or
TV. With Emkay Home the questions go to an OpenVoiceOS in the house instead:
the device keeps the
face, the wake word, the microphone and the speaker; the house has the
skills. Every Emkay in the house shares the same assistant.

Setting that up used to be for nerds (`hivemind-core add-client` in a
terminal, a key and a password typed on the device, a TLS certificate). In
Emkay Home:

- Open its page → pick a language and a password → it's running.
- **"Add an Emkay"** shows a QR code. Scan it with the device → Emkay opens as
  a satellite of the house. Nobody sees the word HiveMind, a key or a
  password, and nothing goes by mail (a pairing link in a mail can end up in
  someone's link scanner – the QR code goes straight from screen to device).
- A list of the paired Emkays (kitchen tablet, bedroom phone, the living-room TV…), and a way to
  remove one.

## Get it

You need a machine in the house that is always on – a Raspberry Pi 4/5
(64-bit), an old PC, a VM or a Proxmox LXC container – with Linux on it.
Then one line ([emkay.ai/home](https://emkay.ai/home/) explains it all):

```sh
curl -fsSL https://emkay.ai/home.sh | bash
```

The installer ([`install/home.sh`](install/home.sh)) looks at the machine,
installs Docker if it is missing (Debian, Ubuntu, Raspberry Pi OS, Fedora,
CentOS/RHEL, Mint, Arch, openSUSE, Alpine), puts the setup in
`/opt/emkay-home`, starts it, and ends with the address to open – and a QR
code to scan. Quietly: one line per step on the screen, everything
else in `/tmp/emkay-home-install.log`. In Emkay's languages, after `$LANG`
(or `--lang da`). Running it again updates; `… | bash -s -- --uninstall`
removes it (and asks before deleting any data). In an LXC container, turn on
*nesting* (and *keyctl* if unprivileged) – the installer tells you if it is
missing.

Afterwards, `emkay-home` on the machine looks after it:

```sh
emkay-home              # is it running, its address, a QR code
emkay-home update       # the newest Emkay Home (the same as the one line again)
emkay-home logs         # what the house is doing
emkay-home restart | start | stop
emkay-home uninstall
```

A new Emkay doesn't need the terminal: open the house's address and tap
**Add an Emkay**.

By hand, with Docker already there:

```sh
git clone https://github.com/emkay-voice/emkay-home
cd emkay-home/compose
cp .env.example .env        # time zone, ports
docker compose up -d
```

Then open `http://<that machine>/` on a phone, tablet or PC on the same network and
follow the page. The first start takes a few minutes while OpenVoiceOS
installs its skills.

## How it fits together

```
a device with Emkay                             the house (docker compose, host network)
 ┌───────────────────────┐                      ┌───────────────────────────────────────────┐
 │ face, wake word, mic, │  https://<house>/    │ Caddy ── /          → emkay_home (the page)│
 │ speech, voice         │ ───────────────────► │      └─ /hivemind   → hivemind-core ─┐     │
 │ (Emkay, any browser)  │  wss://…/hivemind    │         (tls internal: the house's   │     │
 └───────────────────────┘                      │          own CA)                     ▼     │
                                                │ ovos_messagebus ◄── ovos_core + skills     │
                                                └───────────────────────────────────────────┘
```

| Service | Image | What |
|---|---|---|
| `ovos_messagebus`, `ovos_core` | [ovos-docker](https://github.com/OpenVoiceOS/ovos-docker)'s own (`smartgic/ovos-*:alpha`) | stock OpenVoiceOS, as ovos-docker's "server" compose runs it – no microphone or speaker in the house; the Emkays are the ears and the voice |
| `emkay_home` | this repo ([`image/`](image/Dockerfile)) | **hivemind-core**, pinned to versions that start, and **the house page** ([`emkay_home/`](emkay_home)) |
| `emkay_home_panel` | this repo ([`panel/`](panel/Dockerfile)) | the stock [OpenVoiceOS control panel](https://github.com/OpenVoiceOS/ovos-control-panel) for the house's OVOS, on localhost |
| `emkay_home_stt`, `emkay_home_tts` | this repo ([`speech/`](speech/Dockerfile)) | speech in the house, when chosen: the stock `ovos-stt-server` with OpenVoiceOS' onnx-asr plugin (a model per language) and `ovos-tts-server` with Piper. Until then they wait, doing nothing |
| `emkay_home_restarter` | `docker:cli` | restarts `ovos_core` (a new language) and the speech servers (a new choice) when the house page asks; the only thing with the Docker socket, and no network |
| `caddy` | `caddy:2` | one https address for everything, with the house's own certificate ([`caddy/Caddyfile`](caddy/Caddyfile)): the house page at `/`, hivemind-core at `/hivemind`, Emkay at `/emkay/`, the control panel on port 8500 |

Emkay Home is a profile and a page on top of stock OpenVoiceOS, not a fork:

- **Emkay's skills and defaults** – [`emkay_home/profile/`](emkay_home/profile)
  is seeded into the OVOS config on the first start: `skills.list` (made by
  [`tools/sync_profile.py`](tools/sync_profile.py) from the same
  `requirements/` app.emkay.ai is built from, so the house and the browser
  stay alike) and `mycroft.conf` (ovos-installer's intent pipeline, "about
  Emkay" instead of ovos-skill-personal). After that they are the house's to
  change.
- **What the house reached on the internet** – `skills.list` adds
  [ovos-network-log](https://github.com/emkay-voice/ovos-network-log): the
  house's OVOS (`ovos_core`) writes the same network log as Emkay in the
  browser, so [Guardian](https://github.com/emkay-voice/ovos-skill-guardian)
  can answer "what did you send today?" and "what just happened?" for the
  house too. Host names and amounts only – never addresses, questions or
  answers.
- **hivemind-core** is used through its own client database, like
  `hivemind-core add-client` – a house set up here can still be looked after
  with the stock CLI (`docker exec -it emkay_home hivemind-core list-clients`).
- **The pairing page** could well go upstream to HiveMind, which has no such
  thing yet.

### Pairing, step by step

1. On the house page (https, behind its password) "Add an Emkay" makes a
   one-time code, valid for 10 minutes, and shows it as a QR code:
   `http://<house>/#t=<code>`.
2. The device opens the **welcome page** (plain http – it may not trust
   the house yet). The code is in the address' fragment, which a browser
   never sends, so it doesn't cross the network in the clear.
3. The welcome page checks whether the device trusts the house's certificate.
   If not, it offers the certificate and a short guide for the device's system;
   if so, it goes straight on to `https://<house>/pair#t=<code>`.
4. That page trades the code (once) for a new hivemind-core client of its
   own and opens Emkay – from the house, `https://<house>/emkay/` – with the
   pairing link `#hivemind=<base64 JSON>`: host, port 443, path `/hivemind`,
   key, password, language. Emkay saves it and is a satellite of the house
   from then on.

### The control panel

The OVOS in the house is looked after with OpenVoiceOS' own control panel, in
Emkay's colours as in Emkay itself ([`panel/emkay_panel.py`](panel/emkay_panel.py)) –
skills and plugins, settings, logs, the message bus – at
`https://<house>:8500/` ("Control panel" on the house page). It sits behind
the house page's sign-in: Caddy asks `emkay_home` first (`forward_auth`), and
for a signed-in browser adds the panel's own token on the way, so there is one
password for the whole house and the token is never shown. A browser that
isn't signed in is sent to the house page and back. The panel edits the same
`mycroft.conf` as `ovos_core` and asks ovos-core to install skills, so they
land where they run. `PANEL_PORT` in `.env` moves it.

### Speech: on the devices, or in the house

Every Emkay can hear and speak by itself, in the browser – that works
everywhere. On a strong machine the house can do it for all of them instead,
better and faster than a phone or tablet: "Speech" on the house page, *on the devices*
or *in the house*. The house looks at the machine (cores, memory) and
suggests which. Nobody picks plugins or models.

In the house, OpenVoiceOS' own servers do the work: `ovos-stt-server` with
[ovos-stt-plugin-onnx-asr](https://github.com/OpenVoiceOS/ovos-stt-plugin-onnx-asr)
(no torch; a model made for each language, loaded the first time that
language is heard) and `ovos-tts-server` with Piper. For Danish the house
names NVIDIA's Danish Parakeet, which hears Danish best of everything
measured, at a fifth of a second a command on four cores
([docs/danish-speech.md](docs/danish-speech.md)). They have their own
config, so the house's OVOS is left alone. Caddy serves them at
`/speech/stt/` and `/speech/tts/`, only for a paired Emkay (its HiveMind key
as a Bearer token). The pairing link tells a new Emkay about it; one paired
earlier asks `/api/house-info`. The first start downloads the models, a few
minutes. Using it from Emkay is
[emkay#39](https://github.com/emkay-voice/emkay/issues/39).

`python tools/speak.py <house> pairing.json` tries it out the way an Emkay
would (the e2e workflow does): the house says something and hears it back,
with how long each took.

### Emkay, served from the house

The Emkays load Emkay itself from the house too, not from the internet
([emkay#30](https://github.com/emkay-voice/emkay/issues/30)). Emkay is a
static site, and every deploy of app.emkay.ai is also published as one
download (the release [`site`](https://github.com/emkay-voice/emkay/releases/tag/site)).
`emkay_home` fetches it on the first start and then once a day when there is
a newer build (checked against its sha256, switched in one step), and Caddy
serves it at `/emkay/`. The house page shows which build it serves, with
"Look for a newer one". Until it has been fetched, a paired device opens
app.emkay.ai, which talks to the house the same way. `EMKAY_URL` in `.env`
can point the Emkays at another Emkay instead.

### Languages

Emkay Home speaks Emkay's languages – English, Danish, German, Spanish,
Catalan, Galician, Basque, French, Italian, Dutch and Portuguese (Portugal
and Brazil) – with Emkay's words for things, so the house page and the Emkays
read alike. The texts are in [`emkay_home/locale/`](emkay_home/locale), one
`.dialog` file per text like an OVOS skill (and like Emkay), so OVOS'
translation tooling can read them. The page follows the house's language,
else the browser's. Only English and Danish were written by someone who
speaks them; the others need a native speaker's look.

## Home Assistant

**Connect to my Home Assistant** on the house page: type Home Assistant's
address, log in on Home Assistant's own page, and you're back. The house gets
a long-lived token of its own (nobody types one, and Home Assistant's
password never passes through the house), kept in `/data/ha.json`.
**Disconnect** gives the token back to Home Assistant.

Then, with the [OpenVoiceOS integration](https://github.com/andlo/ha-ovos-integration)
in Home Assistant:

- **The house** is a device there (accept it once under *Discovered*), with
  its control panel's settings, skills and backups.
- **Every Emkay** paired with the house is its own device, *connected via*
  Emkay Home – volume, listening on/off, state, "say" – added when it
  connects, unavailable while it's away, and gone from Home Assistant when
  you remove it here. An automation can turn off listening in the bedroom at
  night without touching the kitchen.
- **Lights and heating by voice:** the house's OVOS gets
  [ovos-assist-pipeline-plugin](https://github.com/emkay-voice/ovos-assist-pipeline-plugin),
  so what Home Assistant's Assist knows ("turn off the light on the stairs")
  goes to Home Assistant, from every Emkay.

It runs [ovos-phal-plugin-ha-link](https://github.com/emkay-voice/ovos-phal-plugin-ha-link)
in `emkay_home` (`emkay_home/ha.py`), on the house's bus. The Emkays may put
their answers about themselves (volume, microphone) on that bus –
`hive.ANSWERS` in their hivemind-core permissions, also for Emkays paired
before – and nothing that makes the house do anything.

## Certificates

A browser gives a page the microphone only over https, and an https page may
only open `wss://` – so the device has to trust the house. Emkay Home makes
**its own certificate authority** (Caddy's `tls internal`): offline, private,
nothing leaves the house. It is installed once on each phone, tablet and PC –
the welcome page helps. An accepted "not secure" warning is not enough: the
browser then never asks for the microphone, and Emkay can't be installed as
an app.

Already have a trusted certificate for the house (Home Assistant / Nabu
Casa, a Cloudflare tunnel, Tailscale) or your own domain? See
[docs/certificates.md](docs/certificates.md). Emkay.ai runs no certificate
service, and the house doesn't need the internet for its certificate.

## Roadmap

- A **Home Assistant add-on** (next to [haos-ovos-addons](https://github.com/andlo/haos-ovos-addons)),
  and a Proxmox helper that makes the LXC container itself.
- **Hardware presets** ("private" / "fast", GPU detection), so nobody picks
  STT/TTS plugins by hand.
- Screenshots in the certificate guide; native speakers' look at the texts.

## Development

```sh
python -m venv .venv && .venv/bin/pip install -r image/requirements.txt -e .
EMKAY_HOME_DATA=/tmp/eh/data EMKAY_HOME_OVOS_CONFIG=/tmp/eh/ovos EMKAY_HOME_SITE=/tmp/eh/site \
  HTTP_PORT=8080 HTTPS_PORT=8443 .venv/bin/emkay-home
# Caddy in front of it:
podman run --rm --network host -e HTTP_PORT=8080 -e HTTPS_PORT=8443 \
  -v ./caddy/Caddyfile:/etc/caddy/Caddyfile:ro,Z -v /tmp/eh/site:/emkay-site:ro,z docker.io/library/caddy:2
# and an ovos-messagebus for hivemind-core to talk to
```

[`tools/smoke.py`](tools/smoke.py) walks through the house like a person
would – welcome page, certificate, first start, "Add an Emkay", pairing, the
list – and prints the pairing link:

```sh
python tools/smoke.py 192.168.1.10 --http 8080 --https 8443 [--panel 8500]
```

## License

Apache 2.0, like OpenVoiceOS.
