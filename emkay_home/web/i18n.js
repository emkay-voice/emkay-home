// Emkay Home's texts. English and Danish for now; other languages fall back
// to English until someone who speaks them writes them.

const TEXTS = {
  en: {
    tagline: "OpenVoiceOS for the house",
    footer: "Emkay Home · the OpenVoiceOS your Emkays are satellites of",
    // welcome (plain http): trusting the house
    "welcome.title": "Welcome to Emkay Home",
    "welcome.checking": "Checking the connection…",
    "welcome.trusted": "This device trusts your house. ✓",
    "welcome.continue": "Continue",
    "welcome.need": "One thing first: this device has to trust your house. Emkay Home makes its own certificate – nothing goes via the internet. Install it once, and Emkay may use the microphone.",
    "welcome.download": "Download the certificate",
    "welcome.fp": "Its fingerprint (SHA-256), if you want to compare:",
    "welcome.retry": "I've installed it – try again",
    "welcome.no_ca": "Emkay Home is still making its certificate. Try again in a moment.",
    "welcome.how": "How to install it",
    "guide.android": "Android",
    "guide.android.steps": ["Tap “Download the certificate”.", "Open Settings → Security & privacy → More security settings → Encryption & credentials → Install a certificate → CA certificate (the names vary a little between phones).", "Tap “Install anyway” and pick emkay-home.crt from Downloads.", "Come back here and tap “Try again”."],
    "guide.ios": "iPhone and iPad",
    "guide.ios.steps": ["Open this page in Safari and tap “Download the certificate”, then “Allow”.", "Open Settings → Profile Downloaded → Install.", "Then Settings → General → About → Certificate Trust Settings, and switch on Emkay Home's certificate.", "Come back here and tap “Try again”."],
    "guide.windows": "Windows",
    "guide.windows.steps": ["Download the certificate and open it.", "Install Certificate → Current User → Place all certificates in: Trusted Root Certification Authorities.", "Restart the browser and tap “Try again”."],
    "guide.mac": "Mac",
    "guide.mac.steps": ["Download the certificate and open it – Keychain Access adds it.", "Double-click it in Keychain Access → Trust → When using this certificate: Always Trust.", "Restart the browser and tap “Try again”."],
    "guide.linux": "Linux",
    "guide.linux.steps": ["Chrome/Edge: Settings → Privacy and security → Security → Manage certificates → Authorities → Import.", "Firefox: Settings → Privacy & Security → Certificates → View Certificates → Authorities → Import.", "Tick “Trust this certificate for identifying websites” and tap “Try again”."],
    // pair
    "pair.connecting": "Connecting this Emkay to your house…",
    "pair.expired": "This QR code has expired or was already used. Make a new one on Emkay Home's page.",
    "pair.failed": "That didn't work: {error}",
    "pair.no_code": "There is no code here. Scan the QR code from Emkay Home's page.",
    // first start and login
    "setup.lead": "Welcome! Pick the language of your house and a password for this page.",
    "setup.lang": "Language",
    "setup.password": "Password for Emkay Home (at least 6 characters)",
    "setup.start": "Start",
    "login.lead": "Log in to look after your house.",
    "login.password": "Password",
    "login.go": "Log in",
    "login.wrong": "Wrong password.",
    logout: "Log out",
    // add an Emkay
    "add.title": "Add an Emkay",
    "add.lead": "Give it a name, then scan the code with the phone's or tablet's camera.",
    "add.name": "Name",
    "add.placeholder": "Kitchen tablet",
    "add.show": "Show QR code",
    "add.count": "Works for {m}:{s} more",
    "add.expired": "The code has expired.",
    "add.paired": "{name} is connected ✓",
    "add.done": "Done",
    "add.again": "New code",
    // the list
    "list.title": "Your Emkays",
    "list.empty": "No Emkays yet.",
    "list.seen": "Last seen {when}",
    "list.never": "Not connected yet",
    "list.remove": "Remove",
    "list.confirm": "Remove {name}? It can no longer reach the house.",
    // language
    "lang.title": "Language",
    "lang.lead": "What the house speaks and understands. Skills for a new language are loaded when OpenVoiceOS restarts.",
    "lang.saved": "Saved.",
    // certificate
    "ca.title": "The house's certificate",
    "ca.lead": "Every phone, tablet and PC that uses Emkay with your house trusts this once. It is made here and never leaves the house.",
    "ca.download": "Download",
    error: "Something went wrong ({error}).",
  },
  da: {
    tagline: "OpenVoiceOS til huset",
    footer: "Emkay Home · den OpenVoiceOS dine Emkays er satellitter af",
    "welcome.title": "Velkommen til Emkay Home",
    "welcome.checking": "Tjekker forbindelsen…",
    "welcome.trusted": "Denne enhed stoler på dit hus. ✓",
    "welcome.continue": "Fortsæt",
    "welcome.need": "Først én ting: denne enhed skal stole på dit hus. Emkay Home laver sit eget certifikat – intet går over internettet. Installér det én gang, så må Emkay bruge mikrofonen.",
    "welcome.download": "Hent certifikatet",
    "welcome.fp": "Dets fingeraftryk (SHA-256), hvis du vil sammenligne:",
    "welcome.retry": "Jeg har installeret det – prøv igen",
    "welcome.no_ca": "Emkay Home er ved at lave sit certifikat. Prøv igen om lidt.",
    "welcome.how": "Sådan installerer du det",
    "guide.android": "Android",
    "guide.android.steps": ["Tryk på “Hent certifikatet”.", "Åbn Indstillinger → Sikkerhed og privatliv → Flere sikkerhedsindstillinger → Kryptering og loginoplysninger → Installer et certifikat → CA-certifikat (navnene varierer lidt fra telefon til telefon).", "Tryk på “Installer alligevel”, og vælg emkay-home.crt under Downloads.", "Kom tilbage hertil, og tryk på “Prøv igen”."],
    "guide.ios": "iPhone og iPad",
    "guide.ios.steps": ["Åbn siden i Safari, tryk på “Hent certifikatet” og så “Tillad”.", "Åbn Indstillinger → Profil hentet → Installer.", "Derefter Indstillinger → Generelt → Om → Indstillinger for certifikattillid, og slå Emkay Homes certifikat til.", "Kom tilbage hertil, og tryk på “Prøv igen”."],
    "guide.windows": "Windows",
    "guide.windows.steps": ["Hent certifikatet, og åbn det.", "Installer certifikat → Aktuel bruger → Placer alle certifikater i: Nøglecentre for rodcertifikater, der er tillid til.", "Genstart browseren, og tryk på “Prøv igen”."],
    "guide.mac": "Mac",
    "guide.mac.steps": ["Hent certifikatet, og åbn det – Nøglering tilføjer det.", "Dobbeltklik på det i Nøglering → Tillid → Når dette certifikat bruges: Hav altid tillid.", "Genstart browseren, og tryk på “Prøv igen”."],
    "guide.linux": "Linux",
    "guide.linux.steps": ["Chrome/Edge: Indstillinger → Privatliv og sikkerhed → Sikkerhed → Administrer certifikater → Myndigheder → Importér.", "Firefox: Indstillinger → Privatliv & sikkerhed → Certifikater → Vis certifikater → Autoriteter → Importér.", "Sæt flueben ved at stole på certifikatet til at identificere websteder, og tryk på “Prøv igen”."],
    "pair.connecting": "Forbinder denne Emkay med dit hus…",
    "pair.expired": "QR-koden er udløbet eller allerede brugt. Lav en ny på Emkay Homes side.",
    "pair.failed": "Det gik ikke: {error}",
    "pair.no_code": "Der er ingen kode her. Scan QR-koden fra Emkay Homes side.",
    "setup.lead": "Velkommen! Vælg husets sprog og en adgangskode til denne side.",
    "setup.lang": "Sprog",
    "setup.password": "Adgangskode til Emkay Home (mindst 6 tegn)",
    "setup.start": "Start",
    "login.lead": "Log ind for at passe dit hus.",
    "login.password": "Adgangskode",
    "login.go": "Log ind",
    "login.wrong": "Forkert adgangskode.",
    logout: "Log ud",
    "add.title": "Tilføj en Emkay",
    "add.lead": "Giv den et navn, og scan så koden med telefonens eller tablettens kamera.",
    "add.name": "Navn",
    "add.placeholder": "Køkkentablet",
    "add.show": "Vis QR-kode",
    "add.count": "Virker i {m}:{s} endnu",
    "add.expired": "Koden er udløbet.",
    "add.paired": "{name} er forbundet ✓",
    "add.done": "Færdig",
    "add.again": "Ny kode",
    "list.title": "Dine Emkays",
    "list.empty": "Ingen Emkays endnu.",
    "list.seen": "Sidst set {when}",
    "list.never": "Ikke forbundet endnu",
    "list.remove": "Fjern",
    "list.confirm": "Fjern {name}? Den kan så ikke længere nå huset.",
    "lang.title": "Sprog",
    "lang.lead": "Det sprog huset taler og forstår. Færdigheder til et nyt sprog indlæses, når OpenVoiceOS genstarter.",
    "lang.saved": "Gemt.",
    "ca.title": "Husets certifikat",
    "ca.lead": "Hver telefon, tablet og pc der bruger Emkay med dit hus, skal stole på det én gang. Det er lavet her og forlader aldrig huset.",
    "ca.download": "Hent",
    error: "Noget gik galt ({error}).",
  },
};

let lang = (navigator.language || "en").slice(0, 2).toLowerCase();

/** Use the house's language (e.g. "da-dk") when it is known. */
export function setLang(code) {
  if (code) lang = code.slice(0, 2).toLowerCase();
  document.documentElement.lang = lang;
}

export function t(key, vars = {}) {
  const v = (TEXTS[lang] && TEXTS[lang][key]) ?? TEXTS.en[key] ?? key;
  return typeof v === "string" ? v.replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? "") : v;
}

/** Fill every [data-t] element with its text (and [data-t-placeholder]). */
export function translate(root = document) {
  root.querySelectorAll("[data-t]").forEach((el) => { el.textContent = t(el.dataset.t); });
  root.querySelectorAll("[data-t-placeholder]").forEach((el) => { el.placeholder = t(el.dataset.tPlaceholder); });
}

export function when(ts) {
  try {
    return new Intl.DateTimeFormat(lang, { dateStyle: "medium", timeStyle: "short" }).format(new Date(ts * 1000));
  } catch { return new Date(ts * 1000).toLocaleString(); }
}
