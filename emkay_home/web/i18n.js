// Emkay Home's texts, in Emkay's languages and the way Emkay does it
// (web/i18n.js there), so the house and the phones speak alike.
//
// The texts live in emkay_home/locale/<lang>/<key>.dialog – the layout and
// format of an OVOS skill's dialogs, so OVOS' translation tooling reads them;
// the page serves them gathered as texts.json. To add a language, add its
// folder (and its name in settings.LANGS).
//
// Which language: the house's (OVOS' `lang`, chosen at the first start) once
// it is known, else the browser's. A language without texts falls back to
// English.
//
// An element is translated by data-i18n="key" (its text) or
// data-i18n-placeholder="key".

export const TEXTS = await fetch(new URL("texts.json", import.meta.url))
  .then((r) => (r.ok ? r.json() : {})).catch(() => ({}));
TEXTS["en-us"] ??= {};
const LANGS = Object.keys(TEXTS);

/** As Emkay's langs.js: the same code, else the same base language. */
export function matchLang(code, langs = LANGS) {
  const c = String(code || "").toLowerCase().replace("_", "-");
  if (!c) return null;
  return langs.find((l) => l.toLowerCase() === c)
    ?? langs.find((l) => l.split("-")[0].toLowerCase() === c.split("-")[0])
    ?? null;
}

const pick = (code) => matchLang(code) || "en-us";
let current = pick((navigator.languages || [])[0] || navigator.language);

export function lang() { return current; }

/** Use the house's language (e.g. "da-dk") when it is known. */
export function setLang(code) {
  if (code) current = pick(code);
  document.documentElement.lang = current;
}

export function has(key) {
  return key in (TEXTS[current] || {}) || key in TEXTS["en-us"];
}

/** The text for `key`, with {name} placeholders filled from `vars`. */
export function t(key, vars = {}) {
  const s = TEXTS[current]?.[key] ?? TEXTS["en-us"][key] ?? key;
  return s.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? String(vars[k]) : m));
}

/** Translate the marked elements under `root`. */
export function apply(root = document) {
  document.documentElement.lang = current;
  for (const el of root.querySelectorAll("[data-i18n]")) el.textContent = t(el.dataset.i18n);
  for (const el of root.querySelectorAll("[data-i18n-placeholder]")) el.placeholder = t(el.dataset.i18nPlaceholder);
}

export function when(ts) {
  try {
    return new Intl.DateTimeFormat(current, { dateStyle: "medium", timeStyle: "short" }).format(new Date(ts * 1000));
  } catch { return new Date(ts * 1000).toLocaleString(); }
}
