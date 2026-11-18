// The house page (https): first start, log in, add an Emkay, the paired
// Emkays, the language and the certificate.
import { apply, setLang, t, when } from "./i18n.js";

const $ = (id) => document.getElementById(id);
const show = (id, on = true) => $(id).classList.toggle("hidden", !on);

async function api(path, body) {
  const r = await fetch(path, body === undefined ? { cache: "no-store" } : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  if (!r.ok) throw Object.assign(new Error(String(r.status)), { status: r.status });
  return r.json();
}

function fillLangs(select, langs, current) {
  select.replaceChildren(...Object.entries(langs).map(([code, name]) => {
    const o = new Option(name, code);
    o.selected = code === current;
    return o;
  }));
}

// --- first start and log in -----------------------------------------------

function guessLang(langs) {
  const nav = (navigator.language || "en-US").toLowerCase();
  return langs[nav] ? nav : Object.keys(langs).find((c) => c.startsWith(nav.slice(0, 2))) || "en-us";
}

$("setup-lang").onchange = (e) => { setLang(e.target.value); apply(); };

$("setup").onsubmit = async (e) => {
  e.preventDefault();
  const f = new FormData(e.target);
  try {
    await api("/api/setup", { lang: f.get("lang"), password: f.get("password") });
    start();
  } catch (err) {
    $("setup-error").textContent = t("error", { error: err.message });
    show("setup-error");
  }
};

$("login").onsubmit = async (e) => {
  e.preventDefault();
  try {
    await api("/api/login", { password: $("login-pw").value });
    start();
  } catch {
    show("login-error");
  }
};

$("logout").onclick = async () => { await api("/api/logout", {}); location.reload(); };

// --- the paired Emkays ------------------------------------------------------

async function refresh() {
  const { clients } = await api("/api/clients");
  show("empty", clients.length === 0);
  $("emkays").replaceChildren(...clients.map((c) => {
    const li = document.createElement("li");
    const who = document.createElement("span");
    who.textContent = c.name;
    const seen = document.createElement("span");
    seen.className = "seen";
    seen.textContent = c.last_seen ? t("list.seen", { when: when(c.last_seen) }) : t("list.never");
    who.append(seen);
    const rm = document.createElement("button");
    rm.className = "danger";
    rm.textContent = t("list.remove");
    rm.onclick = async () => {
      if (!confirm(t("list.confirm", { name: c.name }))) return;
      await api("/api/clients/remove", { id: c.id });
      refresh();
    };
    li.append(who, rm);
    return li;
  }));
}

// --- add an Emkay -----------------------------------------------------------

let timer = null;

function closeQr() {
  clearInterval(timer);
  show("qr", false);
  show("add");
  $("add-name").value = "";
}

async function newCode(name) {
  clearInterval(timer);
  const inv = await api("/api/invite", { name });
  $("qr-code").innerHTML = inv.qr;   // an SVG made by the house (segno)
  show("qr-code"); show("qr-count"); show("qr-done", false); show("qr-again", false);
  show("add", false);
  show("qr");
  const ends = Date.now() + inv.seconds * 1000;
  let tick = 0;
  const step = async () => {
    const left = Math.max(0, Math.round((ends - Date.now()) / 1000));
    $("qr-count").textContent = left ? t("add.count", { m: Math.floor(left / 60), s: String(left % 60).padStart(2, "0") }) : t("add.expired");
    if (!left) { clearInterval(timer); show("qr-code", false); show("qr-again"); return; }
    if (++tick % 2) return;   // ask the house every other second
    try {
      const st = await api(`/api/invite?code=${encodeURIComponent(inv.code)}`);
      if (st.paired) {
        clearInterval(timer);
        show("qr-code", false); show("qr-count", false);
        $("qr-done").textContent = t("add.paired", { name: name || "Emkay" });
        show("qr-done");
        refresh();
      }
    } catch {}
  };
  step();
  timer = setInterval(step, 1000);
}

$("add").onsubmit = (e) => {
  e.preventDefault();
  newCode($("add-name").value.trim() || $("add-name").placeholder).catch((err) => alert(t("error", { error: err.message })));
};
$("qr-again").onclick = () => newCode($("add-name").value.trim() || $("add-name").placeholder);
$("qr-close").onclick = closeQr;

// --- Emkay, served from the house ---------------------------------------------

let emkayTimer = null;

async function emkay() {
  clearTimeout(emkayTimer);
  let s;
  try { s = await api("/api/emkay"); } catch { return; }
  const b = s.installed;
  const busy = ["checking", "downloading", "unpacking"].includes(s.state);
  let text;
  if (s.mode === "url") text = t("emkay.url", { url: s.url });
  else if (s.state === "downloading") text = t("emkay.downloading", { pct: s.progress == null ? "…" : `${Math.round(s.progress * 100)} %` });
  else if (s.state === "unpacking") text = t("emkay.unpacking");
  else if (s.state === "checking") text = t("emkay.checking");
  else if (b) text = t("emkay.serving", { version: b.version, build: b.build, commit: b.commit });
  else text = t("emkay.none");
  if (s.state === "error") text += " " + t("emkay.error", { error: s.error });
  $("emkay-state").textContent = text;
  $("emkay-open").href = s.serving ? s.house_url : s.url;
  show("emkay-open", s.mode === "url" || !!b);
  show("emkay-update", s.mode === "house" && !busy);
  if (busy) emkayTimer = setTimeout(emkay, 1500);
}

$("emkay-update").onclick = async () => {
  await api("/api/emkay", {});
  setTimeout(emkay, 300);
};

// --- speech: on the phones, or in the house ------------------------------------

let speechTimer = null;

async function speech(fill = true) {
  clearTimeout(speechTimer);
  let s;
  try { s = await api("/api/speech"); } catch { return; }
  const hw = s.hardware;
  if (fill) for (const r of $("speech").elements.where) r.checked = r.value === s.where;
  $("speech-hears").textContent = t("speech.hears", { model: s.hears });
  const where = t(s.suggested.where === "house" ? "speech.house" : "speech.phones").toLowerCase();
  $("speech-machine").textContent = t("speech.machine", { cores: hw.cores, mem: hw.mem_gb ?? "?", gpu: hw.gpu ? t("speech.gpu") : "" })
    + " " + t("speech.suggest", { where });
  $("speech-state").textContent = t(`speech.${s.status.state}`);
  $("speech-state").classList.toggle("ok", s.status.state === "ready");
  if (s.status.state === "starting") speechTimer = setTimeout(() => speech(false), 3000);
}

$("speech").onsubmit = async (e) => {
  e.preventDefault();
  const f = new FormData(e.target);
  await api("/api/speech", { where: f.get("where") });
  show("speech-saved");
  setTimeout(() => show("speech-saved", false), 2000);
  setTimeout(() => speech(false), 500);
};

// --- language -----------------------------------------------------------------

$("lang").onchange = async (e) => {
  await api("/api/lang", { lang: e.target.value });
  setLang(e.target.value);
  apply();
  refresh();
  speech(false);
  show("lang-saved");
  setTimeout(() => show("lang-saved", false), 2000);
};

// --- start --------------------------------------------------------------------

async function start() {
  const info = await api("/api/info");
  setLang(info.lang);
  for (const id of ["setup", "login", "house"]) show(id, false);
  if (!info.setup_done) {
    const guess = guessLang(info.langs);
    fillLangs($("setup-lang"), info.langs, guess);
    setLang(guess);
    show("setup");
  } else if (!info.logged_in) {
    show("login");
  } else {
    fillLangs($("lang"), info.langs, info.lang);
    $("ca-fp").textContent = info.ca ? `SHA-256 ${info.ca.sha256}` : "";
    $("panel-open").href = `https://${location.hostname}:${info.panel_port}/`;
    // signed in on the way to the control panel: on to it
    if (new URLSearchParams(location.search).get("next") === "panel") {
      history.replaceState(null, "", "/");
      location.href = $("panel-open").href;
      return;
    }
    show("house");
    refresh();
    emkay();
    speech();
  }
  apply();
}

start();
