// Pairing, over https: trade the one-time code for this Emkay's own
// connection to the house, and open Emkay with it (#hivemind=…). The code
// and the link only ever live in fragments, which browsers don't send.
import { setLang, t, translate } from "./i18n.js";

const msg = document.getElementById("msg");
const code = (location.hash.match(/[#&]t=([\w-]+)/) || [])[1];
history.replaceState(null, "", location.pathname);   // the code is single-use; don't keep it around

try {
  const info = await (await fetch("/api/info", { cache: "no-store" })).json();
  setLang(info.lang);
} catch {}
translate();

if (!code) {
  msg.textContent = t("pair.no_code");
} else {
  try {
    const r = await fetch("/api/redeem", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code }),
    });
    if (r.status === 410) msg.textContent = t("pair.expired");
    else if (!r.ok) msg.textContent = t("pair.failed", { error: r.status });
    else location.replace((await r.json()).url);
  } catch (e) {
    msg.textContent = t("pair.failed", { error: e.message });
  }
}
