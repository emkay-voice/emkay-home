# Emkay Home

The OpenVoiceOS for the house, with every Emkay in it – phone, tablet, PC or
TV – as its satellite. This add-on is the same house as the normal
installation ([emkay.ai/home](https://emkay.ai/home/)), in one container on
your Home Assistant – an option when the machine Home Assistant runs on has
power to spare for the house too.

## Set it up

1. Start the add-on and open **Open Web UI** (`https://<home assistant>:8443/`).
2. The browser warns about the certificate the first time: the house makes
   its own. The welcome page (`http://<home assistant>:8480/`) explains how to
   trust it on each device.
3. Pick a language and a password, and add each Emkay with a QR code.

The house page's **Home Assistant** card connects the house to this Home
Assistant (`http://homeassistant.local:8123`), and with the
[OpenVoiceOS integration](https://github.com/andlo/ha-ovos-integration) the
house and every Emkay become devices here.

## Options

| Option | Default | |
|---|---|---|
| `https_port` | 8443 | The house page and the Emkays |
| `http_port` | 8480 | The welcome page, and the house's certificate |
| `panel_port` | 8500 | The OpenVoiceOS control panel |
| `names` | | More names the house may be opened by, comma-separated |

Change a port only if something else on Home Assistant uses it; the paired
Emkays have to be added again when `https_port` changes.

## What is kept

Everything – the password, the paired Emkays, OVOS' settings and skills, the
house's certificate authority – is in the add-on's own storage, so it is in
Home Assistant's backups. The speech models and Emkay itself are downloaded
again when needed and are left out of them.

## Speech in the house

**Speech** on the house page works here too: the house picks what fits the
machine. On a small Home Assistant, or a busy one, leave speech on the devices.
