# Certificates

Emkay needs the house over **https**: a browser gives a page the microphone
only on a secure page, and lets an https page open only `wss://`. So the
phone has to trust the certificate the house shows.

Tested on Android (Edge), with this layout – one https address, hivemind-core
behind `/hivemind` ([emkay#33](https://github.com/emkay-voice/emkay/issues/33)):

| | self-signed, warning accepted | the house's own CA installed |
|---|---|---|
| secure context | ✅ | ✅ |
| `wss://` to hivemind-core | ✅ | ✅ |
| service worker | ❌ | ✅ |
| install as an app | ❌ | ✅ |
| microphone | ❌ – never asks | ✅ |

## The default: the house's own CA

Caddy's `tls internal` makes a certificate authority on the first start
(in the `caddy_data` volume) and certificates from it for whatever LAN
address or local name the house is opened by. Emkay Home only allows the
house's own names (`/tls-ask`): private IP addresses, `*.local`, `*.lan`,
`*.home.arpa`, `*.internal`, names without a dot, and the names in
`EMKAY_HOME_NAMES`.

- Private and offline: nothing is asked of the internet, nothing is
  published (no Certificate Transparency logs).
- Install it once per device: `http://<house>/` shows how, for Android,
  iPhone/iPad, Windows, Mac and Linux, with the fingerprint to compare.
- **Keep the `caddy_data` volume.** A new CA means every device has to trust
  the new one.

## A certificate the house already has

If the house already has a name with a trusted certificate, Emkay Home can
use that instead – nothing to install on phones. Point the Caddyfile at it,
for example:

```caddyfile
emkay.example.dk {
	tls /certs/fullchain.pem /certs/privkey.pem
	# … the same handle blocks as the https:// site
}
```

- **Home Assistant / Nabu Casa, a Cloudflare tunnel:** these reach the house
  from the internet. Fine for a name you already trust, but a route to the
  house through someone else's servers – think about what you open.
- **Tailscale:** `tailscale cert` gives a trusted certificate for the
  machine's `*.ts.net` name; phones on the tailnet reach it.

## Bring your own domain

With a domain of your own at a DNS provider with an API (Cloudflare and most
others), Emkay Home can get a Let's Encrypt certificate for e.g.
`emkay.your-domain.dk` by itself with a DNS-01 challenge: the house is never
reachable from outside, and only your DNS token is used – nothing goes
through emkay.ai. It needs a Caddy build with your provider's DNS plugin
(e.g. `caddy-dns/cloudflare`):

```caddyfile
emkay.your-domain.dk {
	tls {
		dns cloudflare {env.CLOUDFLARE_API_TOKEN}
	}
	# … the same handle blocks as the https:// site
}
```

and a local DNS entry (router, Pi-hole) pointing the name to the house's
LAN address. The price: the house goes online every few weeks to renew, and
the name appears in the public Certificate Transparency logs.

Not planned: a certificate service run by emkay.ai.
