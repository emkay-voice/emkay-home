// The welcome page, over plain http: does this device trust the house's
// certificate yet? If so, on to https (the house page, or – with a code
// from a QR code – pairing). If not, help install it.
import { setLang, t, translate } from "./i18n.js";

const $ = (id) => document.getElementById(id);
const code = (location.hash.match(/[#&]t=([\w-]+)/) || [])[1];
let info;

function httpsBase() {
  const port = info.https_port === 443 ? "" : `:${info.https_port}`;
  return `https://${location.hostname}${port}`;
}

/** An https request to the house only succeeds once the certificate is trusted. */
async function trusted() {
  try {
    await fetch(`${httpsBase()}/ping`, { mode: "no-cors", cache: "no-store" });
    return true;
  } catch { return false; }
}

function next() {
  location.replace(code ? `${httpsBase()}/pair#t=${code}` : `${httpsBase()}/`);
}

function guides() {
  const ua = navigator.userAgent;
  const mine = /Android/i.test(ua) ? "android" : /iPhone|iPad|iPod/i.test(ua) || (/Mac/.test(ua) && navigator.maxTouchPoints > 1) ? "ios"
    : /Windows/i.test(ua) ? "windows" : /Mac/i.test(ua) ? "mac" : "linux";
  const order = [mine, ...["android", "ios", "windows", "mac", "linux"].filter((o) => o !== mine)];
  $("guides").replaceChildren(...order.map((os) => {
    const d = document.createElement("details");
    d.open = os === mine;
    const s = document.createElement("summary");
    s.textContent = t(`guide.${os}`);
    const ol = document.createElement("ol");
    for (const step of t(`guide.${os}.steps`)) {
      const li = document.createElement("li");
      li.textContent = step;
      ol.append(li);
    }
    d.append(s, ol);
    return d;
  }));
}

async function check() {
  $("checking").classList.remove("hidden");
  $("trusted").classList.add("hidden");
  $("need").classList.add("hidden");
  const ok = await trusted();
  $("checking").classList.add("hidden");
  if (ok) {
    $("trusted").classList.remove("hidden");
    // straight on when a QR code brought us here – nothing to decide
    if (code) next();
    return;
  }
  $("need").classList.remove("hidden");
  $("no-ca").classList.toggle("hidden", !!info.ca);
  $("ca").classList.toggle("hidden", !info.ca);
  if (info.ca) $("fp").textContent = info.ca.sha256;
}

info = await (await fetch("/api/info", { cache: "no-store" })).json();
setLang(info.lang);
translate();
guides();
$("continue").onclick = next;
$("retry").onclick = check;
check();
