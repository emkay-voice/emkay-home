#!/usr/bin/env bash
# Emkay Home – the installer.
#
#   curl -fsSL https://emkay.ai/home.sh | bash
#
# Sets up Emkay Home on a Linux machine that is always on – a Raspberry Pi 4/5,
# an old PC, a VM or an LXC container: installs Docker if it is missing, puts
# Emkay Home's compose setup in /opt/emkay-home, starts it, and ends by
# showing the address to open (and a QR code for the phone).
#
# Running it again updates Emkay Home (new images, the newest compose files;
# your .env and all data are kept).
#
# Options (or the environment variables in brackets):
#   --dir DIR          where the setup goes            [EMKAY_HOME_DIR, /opt/emkay-home]
#   --http-port N      the house's http port           [HTTP_PORT, 80 – or 8080 if taken]
#   --https-port N     the house's https port          [HTTPS_PORT, 443 – or 8443 if taken]
#   --ref REF          which emkay-home to install     [EMKAY_HOME_REF, main]
#   --lang LANG        the installer's language        [EMKAY_HOME_LANG, else $LANG]
#   --uninstall        stop and remove Emkay Home (asks before deleting data)
#   --status           the house's state, address and QR code (what
#                      `emkay-home` shows; nothing is changed)
#
# EMKAY_HOME_BUILD=1 builds Emkay Home's image here instead of pulling it
# (it is built here anyway when it can't be pulled).
#
# How it is built, for whoever extends it:
#   * Everything the user reads goes through `say KEY` – the texts are in the
#     TEXTS table below, in Emkay's twelve languages. A new text: add a line
#     per language (English is the fallback). A new language: add its lines
#     and its code in pick_lang.
#   * Every slow or noisy step goes through `step KEY command…`: one line with
#     a spinner on screen, all the command's output in the log file
#     ($LOG). Keep it that way – the screen shows what happens, the log shows
#     how.
#   * Docker is installed per distribution family in install_docker; add a
#     family there.
#   * The compose files come from GitHub (raw) at $REF, so the installer and
#     the repo never drift apart; the installer itself holds no copy of them.
set -o pipefail
# Work from / : the shell may stand in a folder that is gone (in
# /opt/emkay-home/compose when it was removed, say), and docker compose
# refuses to run from a folder that doesn't exist. Every path here is absolute.
cd / 2>/dev/null || true

# --- settings -----------------------------------------------------------------

DIR="${EMKAY_HOME_DIR:-/opt/emkay-home}"
REF="${EMKAY_HOME_REF:-main}"
RAW="https://raw.githubusercontent.com/emkay-voice/emkay-home"
HTTP_PORT="${HTTP_PORT:-}"
HTTPS_PORT="${HTTPS_PORT:-}"
UI_LANG="${EMKAY_HOME_LANG:-}"
UNINSTALL=0
STATUS=0
LOG="/tmp/emkay-home-install.log"

while [ $# -gt 0 ]; do
  case "$1" in
    --dir) DIR="$2"; shift ;;
    --http-port) HTTP_PORT="$2"; shift ;;
    --https-port) HTTPS_PORT="$2"; shift ;;
    --ref) REF="$2"; shift ;;
    --lang) UI_LANG="$2"; shift ;;
    --uninstall) UNINSTALL=1 ;;
    --status) STATUS=1 ;;
    -h|--help) sed -n '2,22p' "$0" 2>/dev/null | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

# --- look and feel --------------------------------------------------------------

# Colours only on a terminal; Emkay's blue (#22a7f0 ≈ 256-colour 39).
if [ -t 1 ]; then
  C_ACCENT=$'\e[38;5;39m'; C_OK=$'\e[38;5;78m'; C_BAD=$'\e[38;5;203m'; C_WARN=$'\e[38;5;221m'
  C_DIM=$'\e[38;5;245m'; C_BOLD=$'\e[1m'; C_OFF=$'\e[0m'; TTY=1
else
  C_ACCENT=; C_OK=; C_BAD=; C_WARN=; C_DIM=; C_BOLD=; C_OFF=; TTY=0
fi

# --- texts ----------------------------------------------------------------------
# lang|key|text – printf-style %s for values. Same words as Emkay ("house",
# "skills"…) and the same tone per language (informal; "vous" in French).

TEXTS='
en|tagline|The OpenVoiceOS for your house
en|hello|Let’s set up Emkay Home on this machine.
en|check|Looking at this machine
en|sys|%s · %s · %s RAM · %s free
en|arch_bad|Emkay Home needs a 64-bit PC (x86_64) or a 64-bit Raspberry Pi (arm64) – this is %s.
en|ram_low|Only %s RAM – Emkay Home wants 2 GB or more (4 GB is better). Carrying on.
en|disk_low|Only %s free – Emkay Home wants about 5 GB. Carrying on.
en|lxc|This is an LXC container.
en|need_root|This needs root: run it as root, or install sudo.
en|need_curl|This needs curl.
en|docker_ok|Docker is here
en|docker_install|Installing Docker
en|docker_unknown|Don’t know how to install Docker on %s – install Docker (with “docker compose”) and run this again.
en|docker_cant|Docker can’t start containers here.
en|lxc_hint|In Proxmox: the container → Options → Features → turn on “nesting” (and “keyctl” for an unprivileged container), restart it and run this again.
en|again|Already installed in %s – updating it.
en|ports|The house: ports %s and %s
en|ports_moved|Port 80 or 443 is taken – the house uses %s and %s
en|files|Fetching Emkay Home’s setup
en|pull|Fetching OpenVoiceOS and Emkay Home – the first time takes a few minutes
en|build|Building Emkay Home on this machine – a minute or two
en|start|Starting the house
en|wait|Waiting for the house to wake up
en|wait_fail|The house didn’t answer in time.
en|ready|Emkay Home is running!
en|updated|Emkay Home is updated and running!
en|open|Open this on your PC or phone:
en|scan|or scan it with the phone:
en|next|There you pick a language and a password – and add your first Emkay.
en|fail|Something went wrong. The last lines of the log (%s):
en|un_ask|Also delete the house’s data – the paired Emkays and its certificate? [y/N] 
en|un_done|Emkay Home is removed.
en|un_kept|Its data is kept – installing again picks it up.
en|status_up|Emkay Home is running (%s of %s services).
en|status_down|Emkay Home isn’t running (%s of %s services) – start it with: emkay-home start
en|add_hint|A new phone: open the address and tap “Add an Emkay”.
en|cmds|More: emkay-home update · logs · restart · uninstall
en|later|Run emkay-home to see this again.
da|tagline|OpenVoiceOS til dit hus
da|hello|Lad os sætte Emkay Home op på denne maskine.
da|check|Kigger på maskinen
da|sys|%s · %s · %s RAM · %s ledigt
da|arch_bad|Emkay Home kræver en 64-bit pc (x86_64) eller en 64-bit Raspberry Pi (arm64) – denne er %s.
da|ram_low|Kun %s RAM – Emkay Home vil gerne have 2 GB eller mere (4 GB er bedre). Fortsætter.
da|disk_low|Kun %s ledigt – Emkay Home vil gerne have omkring 5 GB. Fortsætter.
da|lxc|Dette er en LXC-container.
da|need_root|Det kræver root: kør det som root, eller installér sudo.
da|need_curl|Det kræver curl.
da|docker_ok|Docker er her
da|docker_install|Installerer Docker
da|docker_unknown|Ved ikke, hvordan Docker installeres på %s – installér Docker (med “docker compose”), og kør dette igen.
da|docker_cant|Docker kan ikke starte containere her.
da|lxc_hint|I Proxmox: containeren → Options → Features → slå “nesting” til (og “keyctl” for en unprivileged container), genstart den, og kør dette igen.
da|again|Allerede installeret i %s – opdaterer.
da|ports|Huset: port %s og %s
da|ports_moved|Port 80 eller 443 er optaget – huset bruger %s og %s
da|files|Henter Emkay Homes opsætning
da|pull|Henter OpenVoiceOS og Emkay Home – første gang tager det et par minutter
da|build|Bygger Emkay Home på denne maskine – et minut eller to
da|start|Starter huset
da|wait|Venter på, at huset vågner
da|wait_fail|Huset svarede ikke i tide.
da|ready|Emkay Home kører!
da|updated|Emkay Home er opdateret og kører!
da|open|Åbn dette på din pc eller telefon:
da|scan|eller scan det med telefonen:
da|next|Der vælger du sprog og adgangskode – og tilføjer din første Emkay.
da|fail|Noget gik galt. De sidste linjer i loggen (%s):
da|un_ask|Skal husets data også slettes – de parrede Emkays og certifikatet? [j/N] 
da|un_done|Emkay Home er fjernet.
da|un_kept|Dataene er gemt – en ny installation tager dem med.
da|status_up|Emkay Home kører (%s af %s tjenester).
da|status_down|Emkay Home kører ikke (%s af %s tjenester) – start det med: emkay-home start
da|add_hint|En ny telefon: åbn adressen, og tryk på “Tilføj en Emkay”.
da|cmds|Mere: emkay-home update · logs · restart · uninstall
da|later|Kør emkay-home for at se dette igen.
de|tagline|Das OpenVoiceOS für dein Haus
de|hello|Richten wir Emkay Home auf diesem Rechner ein.
de|check|Schaue mir den Rechner an
de|sys|%s · %s · %s RAM · %s frei
de|arch_bad|Emkay Home braucht einen 64-Bit-PC (x86_64) oder einen 64-Bit-Raspberry-Pi (arm64) – das hier ist %s.
de|ram_low|Nur %s RAM – Emkay Home möchte 2 GB oder mehr (4 GB sind besser). Es geht weiter.
de|disk_low|Nur %s frei – Emkay Home möchte etwa 5 GB. Es geht weiter.
de|lxc|Das ist ein LXC-Container.
de|need_root|Das braucht root: als root ausführen oder sudo installieren.
de|need_curl|Das braucht curl.
de|docker_ok|Docker ist da
de|docker_install|Installiere Docker
de|docker_unknown|Ich weiß nicht, wie Docker auf %s installiert wird – installiere Docker (mit „docker compose“) und starte das hier noch einmal.
de|docker_cant|Docker kann hier keine Container starten.
de|lxc_hint|In Proxmox: der Container → Options → Features → „nesting“ einschalten (und „keyctl“ bei einem unprivilegierten Container), neu starten und das hier noch einmal ausführen.
de|again|Schon in %s installiert – wird aktualisiert.
de|ports|Das Haus: Ports %s und %s
de|ports_moved|Port 80 oder 443 ist belegt – das Haus nutzt %s und %s
de|files|Hole die Einrichtung von Emkay Home
de|pull|Hole OpenVoiceOS und Emkay Home – beim ersten Mal dauert das ein paar Minuten
de|build|Baue Emkay Home auf diesem Rechner – ein, zwei Minuten
de|start|Starte das Haus
de|wait|Warte, bis das Haus wach ist
de|wait_fail|Das Haus hat nicht rechtzeitig geantwortet.
de|ready|Emkay Home läuft!
de|updated|Emkay Home ist aktualisiert und läuft!
de|open|Öffne das auf deinem PC oder Telefon:
de|scan|oder scanne es mit dem Telefon:
de|next|Dort wählst du Sprache und Passwort – und fügst dein erstes Emkay hinzu.
de|fail|Etwas ist schiefgegangen. Die letzten Zeilen des Logs (%s):
de|un_ask|Auch die Daten des Hauses löschen – die gekoppelten Emkays und sein Zertifikat? [j/N] 
de|un_done|Emkay Home ist entfernt.
de|un_kept|Die Daten bleiben – eine neue Installation übernimmt sie.
de|status_up|Emkay Home läuft (%s von %s Diensten).
de|status_down|Emkay Home läuft nicht (%s von %s Diensten) – starte es mit: emkay-home start
de|add_hint|Ein neues Handy: Adresse öffnen und auf „Ein Emkay hinzufügen“ tippen.
de|cmds|Mehr: emkay-home update · logs · restart · uninstall
de|later|Mit emkay-home siehst du das hier wieder.
es|tagline|El OpenVoiceOS para tu casa
es|hello|Vamos a instalar Emkay Home en esta máquina.
es|check|Mirando esta máquina
es|sys|%s · %s · %s de RAM · %s libres
es|arch_bad|Emkay Home necesita un PC de 64 bits (x86_64) o una Raspberry Pi de 64 bits (arm64) – esta es %s.
es|ram_low|Solo %s de RAM – Emkay Home quiere 2 GB o más (mejor 4 GB). Seguimos.
es|disk_low|Solo %s libres – Emkay Home quiere unos 5 GB. Seguimos.
es|lxc|Esto es un contenedor LXC.
es|need_root|Hace falta root: ejecútalo como root o instala sudo.
es|need_curl|Hace falta curl.
es|docker_ok|Docker está aquí
es|docker_install|Instalando Docker
es|docker_unknown|No sé cómo instalar Docker en %s – instala Docker (con «docker compose») y vuelve a ejecutar esto.
es|docker_cant|Docker no puede arrancar contenedores aquí.
es|lxc_hint|En Proxmox: el contenedor → Options → Features → activa «nesting» (y «keyctl» en un contenedor sin privilegios), reinícialo y vuelve a ejecutar esto.
es|again|Ya instalado en %s – actualizando.
es|ports|La casa: puertos %s y %s
es|ports_moved|El puerto 80 o 443 está ocupado – la casa usa %s y %s
es|files|Descargando la configuración de Emkay Home
es|pull|Descargando OpenVoiceOS y Emkay Home – la primera vez tarda unos minutos
es|build|Construyendo Emkay Home en esta máquina – un minuto o dos
es|start|Arrancando la casa
es|wait|Esperando a que la casa despierte
es|wait_fail|La casa no respondió a tiempo.
es|ready|¡Emkay Home está en marcha!
es|updated|¡Emkay Home está actualizado y en marcha!
es|open|Abre esto en tu PC o teléfono:
es|scan|o escanéalo con el teléfono:
es|next|Allí eliges idioma y contraseña – y añades tu primer Emkay.
es|fail|Algo ha salido mal. Las últimas líneas del registro (%s):
es|un_ask|¿Borrar también los datos de la casa – los Emkay emparejados y su certificado? [s/N] 
es|un_done|Emkay Home se ha quitado.
es|un_kept|Los datos se conservan – una nueva instalación los recupera.
es|status_up|Emkay Home está en marcha (%s de %s servicios).
es|status_down|Emkay Home no está en marcha (%s de %s servicios) – arráncalo con: emkay-home start
es|add_hint|Un teléfono nuevo: abre la dirección y toca «Añadir un Emkay».
es|cmds|Más: emkay-home update · logs · restart · uninstall
es|later|Ejecuta emkay-home para ver esto de nuevo.
ca|tagline|L’OpenVoiceOS per a casa teva
ca|hello|Instal·lem Emkay Home en aquesta màquina.
ca|check|Mirant aquesta màquina
ca|sys|%s · %s · %s de RAM · %s lliures
ca|arch_bad|Emkay Home necessita un PC de 64 bits (x86_64) o una Raspberry Pi de 64 bits (arm64) – aquesta és %s.
ca|ram_low|Només %s de RAM – Emkay Home en vol 2 GB o més (millor 4 GB). Continuem.
ca|disk_low|Només %s lliures – Emkay Home en vol uns 5 GB. Continuem.
ca|lxc|Això és un contenidor LXC.
ca|need_root|Cal root: executa-ho com a root o instal·la sudo.
ca|need_curl|Cal curl.
ca|docker_ok|Docker hi és
ca|docker_install|Instal·lant Docker
ca|docker_unknown|No sé com instal·lar Docker a %s – instal·la Docker (amb «docker compose») i torna a executar això.
ca|docker_cant|Docker no pot engegar contenidors aquí.
ca|lxc_hint|A Proxmox: el contenidor → Options → Features → activa «nesting» (i «keyctl» en un contenidor sense privilegis), reinicia’l i torna a executar això.
ca|again|Ja instal·lat a %s – actualitzant.
ca|ports|La casa: ports %s i %s
ca|ports_moved|El port 80 o 443 està ocupat – la casa fa servir %s i %s
ca|files|Baixant la configuració d’Emkay Home
ca|pull|Baixant OpenVoiceOS i Emkay Home – la primera vegada triga uns minuts
ca|build|Construint Emkay Home en aquesta màquina – un minut o dos
ca|start|Engegant la casa
ca|wait|Esperant que la casa es desperti
ca|wait_fail|La casa no ha respost a temps.
ca|ready|Emkay Home funciona!
ca|updated|Emkay Home està actualitzat i funciona!
ca|open|Obre això al teu PC o telèfon:
ca|scan|o escaneja-ho amb el telèfon:
ca|next|Allà tries l’idioma i la contrasenya – i afegeixes el teu primer Emkay.
ca|fail|Alguna cosa ha fallat. Les darreres línies del registre (%s):
ca|un_ask|Vols esborrar també les dades de la casa – els Emkay aparellats i el certificat? [s/N] 
ca|un_done|Emkay Home s’ha eliminat.
ca|un_kept|Les dades es conserven – una nova instal·lació les recupera.
ca|status_up|Emkay Home funciona (%s de %s serveis).
ca|status_down|Emkay Home no funciona (%s de %s serveis) – engega’l amb: emkay-home start
ca|add_hint|Un telèfon nou: obre l’adreça i toca «Afegeix un Emkay».
ca|cmds|Més: emkay-home update · logs · restart · uninstall
ca|later|Executa emkay-home per tornar a veure això.
gl|tagline|O OpenVoiceOS para a túa casa
gl|hello|Imos instalar Emkay Home nesta máquina.
gl|check|Mirando esta máquina
gl|sys|%s · %s · %s de RAM · %s libres
gl|arch_bad|Emkay Home precisa un PC de 64 bits (x86_64) ou unha Raspberry Pi de 64 bits (arm64) – esta é %s.
gl|ram_low|Só %s de RAM – Emkay Home quere 2 GB ou máis (mellor 4 GB). Seguimos.
gl|disk_low|Só %s libres – Emkay Home quere uns 5 GB. Seguimos.
gl|lxc|Isto é un contedor LXC.
gl|need_root|Precisa root: execútao como root ou instala sudo.
gl|need_curl|Precisa curl.
gl|docker_ok|Docker está aquí
gl|docker_install|Instalando Docker
gl|docker_unknown|Non sei como instalar Docker en %s – instala Docker (con «docker compose») e volve executar isto.
gl|docker_cant|Docker non pode iniciar contedores aquí.
gl|lxc_hint|En Proxmox: o contedor → Options → Features → activa «nesting» (e «keyctl» nun contedor sen privilexios), reinícíao e volve executar isto.
gl|again|Xa instalado en %s – actualizando.
gl|ports|A casa: portos %s e %s
gl|ports_moved|O porto 80 ou 443 está ocupado – a casa usa %s e %s
gl|files|Descargando a configuración de Emkay Home
gl|pull|Descargando OpenVoiceOS e Emkay Home – a primeira vez tarda uns minutos
gl|build|Construíndo Emkay Home nesta máquina – un minuto ou dous
gl|start|Iniciando a casa
gl|wait|Agardando a que a casa esperte
gl|wait_fail|A casa non respondeu a tempo.
gl|ready|Emkay Home está en marcha!
gl|updated|Emkay Home está actualizado e en marcha!
gl|open|Abre isto no teu PC ou teléfono:
gl|scan|ou escanéao co teléfono:
gl|next|Alí escolles idioma e contrasinal – e engades o teu primeiro Emkay.
gl|fail|Algo saíu mal. As últimas liñas do rexistro (%s):
gl|un_ask|Borrar tamén os datos da casa – os Emkay emparellados e o seu certificado? [s/N] 
gl|un_done|Emkay Home quitouse.
gl|un_kept|Os datos consérvanse – unha nova instalación recupéraos.
gl|status_up|Emkay Home está en marcha (%s de %s servizos).
gl|status_down|Emkay Home non está en marcha (%s de %s servizos) – iníciao con: emkay-home start
gl|add_hint|Un teléfono novo: abre o enderezo e toca «Engadir un Emkay».
gl|cmds|Máis: emkay-home update · logs · restart · uninstall
gl|later|Executa emkay-home para ver isto de novo.
eu|tagline|Zure etxerako OpenVoiceOS-a
eu|hello|Instala dezagun Emkay Home makina honetan.
eu|check|Makina honi begiratzen
eu|sys|%s · %s · %s RAM · %s libre
eu|arch_bad|Emkay Home-k 64 biteko PC bat (x86_64) edo 64 biteko Raspberry Pi bat (arm64) behar du – hau %s da.
eu|ram_low|%s RAM bakarrik – Emkay Home-k 2 GB edo gehiago nahi ditu (4 GB hobe). Jarraitzen.
eu|disk_low|%s libre bakarrik – Emkay Home-k 5 GB inguru nahi ditu. Jarraitzen.
eu|lxc|LXC edukiontzi bat da hau.
eu|need_root|Root behar da: exekutatu root gisa, edo instalatu sudo.
eu|need_curl|curl behar da.
eu|docker_ok|Docker hemen dago
eu|docker_install|Docker instalatzen
eu|docker_unknown|Ez dakit Docker nola instalatu %s-n – instalatu Docker («docker compose»-rekin) eta exekutatu hau berriro.
eu|docker_cant|Docker-ek ezin ditu edukiontziak hemen abiarazi.
eu|lxc_hint|Proxmox-en: edukiontzia → Options → Features → aktibatu «nesting» (eta «keyctl» pribilegiorik gabeko edukiontzi batean), berrabiarazi eta exekutatu hau berriro.
eu|again|Dagoeneko %s-n instalatuta – eguneratzen.
eu|ports|Etxea: %s eta %s atakak
eu|ports_moved|80 edo 443 ataka hartuta dago – etxeak %s eta %s erabiltzen ditu
eu|files|Emkay Home-ren konfigurazioa deskargatzen
eu|pull|OpenVoiceOS eta Emkay Home deskargatzen – lehen aldian minutu batzuk behar dira
eu|build|Emkay Home makina honetan eraikitzen – minutu bat edo bi
eu|start|Etxea abiarazten
eu|wait|Etxea esnatu arte itxaroten
eu|wait_fail|Etxeak ez du garaiz erantzun.
eu|ready|Emkay Home martxan dago!
eu|updated|Emkay Home eguneratuta eta martxan dago!
eu|open|Ireki hau zure PCan edo telefonoan:
eu|scan|edo eskaneatu telefonoarekin:
eu|next|Han hizkuntza eta pasahitza aukeratzen dituzu – eta zure lehen Emkay-a gehitzen duzu.
eu|fail|Zerbaitek huts egin du. Erregistroaren azken lerroak (%s):
eu|un_ask|Etxearen datuak ere ezabatu – parekatutako Emkayak eta bere ziurtagiria? [b/E] 
eu|un_done|Emkay Home kendu da.
eu|un_kept|Datuak gordetzen dira – instalazio berri batek berreskuratzen ditu.
eu|status_up|Emkay Home martxan dago (%s/%s zerbitzu).
eu|status_down|Emkay Home ez dago martxan (%s/%s zerbitzu) – abiarazi honela: emkay-home start
eu|add_hint|Telefono berri bat: ireki helbidea eta sakatu «Gehitu Emkay bat».
eu|cmds|Gehiago: emkay-home update · logs · restart · uninstall
eu|later|Exekutatu emkay-home hau berriro ikusteko.
fr|tagline|L’OpenVoiceOS pour votre maison
fr|hello|Installons Emkay Home sur cette machine.
fr|check|J’examine cette machine
fr|sys|%s · %s · %s de RAM · %s libres
fr|arch_bad|Emkay Home a besoin d’un PC 64 bits (x86_64) ou d’un Raspberry Pi 64 bits (arm64) – celui-ci est %s.
fr|ram_low|Seulement %s de RAM – Emkay Home veut 2 Go ou plus (4 Go, c’est mieux). On continue.
fr|disk_low|Seulement %s libres – Emkay Home veut environ 5 Go. On continue.
fr|lxc|C’est un conteneur LXC.
fr|need_root|Il faut root : lancez-le en root, ou installez sudo.
fr|need_curl|Il faut curl.
fr|docker_ok|Docker est là
fr|docker_install|Installation de Docker
fr|docker_unknown|Je ne sais pas installer Docker sur %s – installez Docker (avec « docker compose ») et relancez ceci.
fr|docker_cant|Docker ne peut pas lancer de conteneurs ici.
fr|lxc_hint|Dans Proxmox : le conteneur → Options → Features → activez « nesting » (et « keyctl » pour un conteneur non privilégié), redémarrez-le et relancez ceci.
fr|again|Déjà installé dans %s – mise à jour.
fr|ports|La maison : ports %s et %s
fr|ports_moved|Le port 80 ou 443 est pris – la maison utilise %s et %s
fr|files|Récupération de la configuration d’Emkay Home
fr|pull|Récupération d’OpenVoiceOS et d’Emkay Home – la première fois prend quelques minutes
fr|build|Construction d’Emkay Home sur cette machine – une minute ou deux
fr|start|Démarrage de la maison
fr|wait|J’attends que la maison se réveille
fr|wait_fail|La maison n’a pas répondu à temps.
fr|ready|Emkay Home fonctionne !
fr|updated|Emkay Home est à jour et fonctionne !
fr|open|Ouvrez ceci sur votre PC ou téléphone :
fr|scan|ou scannez-le avec le téléphone :
fr|next|Là, vous choisissez la langue et un mot de passe – et ajoutez votre premier Emkay.
fr|fail|Un problème est survenu. Les dernières lignes du journal (%s) :
fr|un_ask|Supprimer aussi les données de la maison – les Emkay appairés et son certificat ? [o/N] 
fr|un_done|Emkay Home est supprimé.
fr|un_kept|Les données sont gardées – une nouvelle installation les reprend.
fr|status_up|Emkay Home fonctionne (%s services sur %s).
fr|status_down|Emkay Home ne fonctionne pas (%s services sur %s) – démarrez-le avec : emkay-home start
fr|add_hint|Un nouveau téléphone : ouvrez l’adresse et touchez « Ajouter un Emkay ».
fr|cmds|Plus : emkay-home update · logs · restart · uninstall
fr|later|Lancez emkay-home pour revoir ceci.
it|tagline|L’OpenVoiceOS per la tua casa
it|hello|Installiamo Emkay Home su questa macchina.
it|check|Do un’occhiata a questa macchina
it|sys|%s · %s · %s di RAM · %s liberi
it|arch_bad|Emkay Home richiede un PC a 64 bit (x86_64) o un Raspberry Pi a 64 bit (arm64) – questo è %s.
it|ram_low|Solo %s di RAM – Emkay Home vuole 2 GB o più (meglio 4 GB). Continuo.
it|disk_low|Solo %s liberi – Emkay Home vuole circa 5 GB. Continuo.
it|lxc|Questo è un container LXC.
it|need_root|Serve root: eseguilo come root o installa sudo.
it|need_curl|Serve curl.
it|docker_ok|Docker c’è
it|docker_install|Installazione di Docker
it|docker_unknown|Non so come installare Docker su %s – installa Docker (con «docker compose») ed esegui di nuovo questo.
it|docker_cant|Docker non riesce ad avviare container qui.
it|lxc_hint|In Proxmox: il container → Options → Features → attiva «nesting» (e «keyctl» per un container non privilegiato), riavvialo ed esegui di nuovo questo.
it|again|Già installato in %s – aggiornamento.
it|ports|La casa: porte %s e %s
it|ports_moved|La porta 80 o 443 è occupata – la casa usa %s e %s
it|files|Scarico la configurazione di Emkay Home
it|pull|Scarico OpenVoiceOS ed Emkay Home – la prima volta ci vuole qualche minuto
it|build|Costruisco Emkay Home su questa macchina – un minuto o due
it|start|Avvio la casa
it|wait|Aspetto che la casa si svegli
it|wait_fail|La casa non ha risposto in tempo.
it|ready|Emkay Home è in funzione!
it|updated|Emkay Home è aggiornato e in funzione!
it|open|Apri questo sul tuo PC o telefono:
it|scan|oppure scansionalo con il telefono:
it|next|Lì scegli lingua e password – e aggiungi il tuo primo Emkay.
it|fail|Qualcosa è andato storto. Le ultime righe del registro (%s):
it|un_ask|Cancellare anche i dati della casa – gli Emkay abbinati e il suo certificato? [s/N] 
it|un_done|Emkay Home è stato rimosso.
it|un_kept|I dati restano – una nuova installazione li riprende.
it|status_up|Emkay Home è in funzione (%s servizi su %s).
it|status_down|Emkay Home non è in funzione (%s servizi su %s) – avvialo con: emkay-home start
it|add_hint|Un nuovo telefono: apri l’indirizzo e tocca «Aggiungi un Emkay».
it|cmds|Altro: emkay-home update · logs · restart · uninstall
it|later|Esegui emkay-home per rivedere questo.
nl|tagline|Het OpenVoiceOS voor je huis
nl|hello|Laten we Emkay Home op deze machine zetten.
nl|check|Ik bekijk deze machine
nl|sys|%s · %s · %s RAM · %s vrij
nl|arch_bad|Emkay Home heeft een 64-bit pc (x86_64) of een 64-bit Raspberry Pi (arm64) nodig – dit is %s.
nl|ram_low|Maar %s RAM – Emkay Home wil 2 GB of meer (4 GB is beter). We gaan door.
nl|disk_low|Maar %s vrij – Emkay Home wil ongeveer 5 GB. We gaan door.
nl|lxc|Dit is een LXC-container.
nl|need_root|Dit heeft root nodig: voer het uit als root, of installeer sudo.
nl|need_curl|Dit heeft curl nodig.
nl|docker_ok|Docker is er
nl|docker_install|Docker installeren
nl|docker_unknown|Ik weet niet hoe Docker op %s geïnstalleerd wordt – installeer Docker (met ‘docker compose’) en voer dit opnieuw uit.
nl|docker_cant|Docker kan hier geen containers starten.
nl|lxc_hint|In Proxmox: de container → Options → Features → zet ‘nesting’ aan (en ‘keyctl’ voor een unprivileged container), herstart hem en voer dit opnieuw uit.
nl|again|Al geïnstalleerd in %s – bijwerken.
nl|ports|Het huis: poorten %s en %s
nl|ports_moved|Poort 80 of 443 is bezet – het huis gebruikt %s en %s
nl|files|Instellingen van Emkay Home ophalen
nl|pull|OpenVoiceOS en Emkay Home ophalen – de eerste keer duurt dat een paar minuten
nl|build|Emkay Home bouwen op deze machine – een minuut of twee
nl|start|Het huis starten
nl|wait|Wachten tot het huis wakker is
nl|wait_fail|Het huis antwoordde niet op tijd.
nl|ready|Emkay Home draait!
nl|updated|Emkay Home is bijgewerkt en draait!
nl|open|Open dit op je pc of telefoon:
nl|scan|of scan het met de telefoon:
nl|next|Daar kies je een taal en een wachtwoord – en voeg je je eerste Emkay toe.
nl|fail|Er ging iets mis. De laatste regels van het logboek (%s):
nl|un_ask|Ook de gegevens van het huis wissen – de gekoppelde Emkays en het certificaat? [j/N] 
nl|un_done|Emkay Home is verwijderd.
nl|un_kept|De gegevens blijven – een nieuwe installatie neemt ze mee.
nl|status_up|Emkay Home draait (%s van %s diensten).
nl|status_down|Emkay Home draait niet (%s van %s diensten) – start het met: emkay-home start
nl|add_hint|Een nieuwe telefoon: open het adres en tik op ‘Een Emkay toevoegen’.
nl|cmds|Meer: emkay-home update · logs · restart · uninstall
nl|later|Voer emkay-home uit om dit opnieuw te zien.
pt|tagline|O OpenVoiceOS para a sua casa
pt|hello|Vamos instalar o Emkay Home nesta máquina.
pt|check|A ver esta máquina
pt|sys|%s · %s · %s de RAM · %s livres
pt|arch_bad|O Emkay Home precisa de um PC de 64 bits (x86_64) ou de um Raspberry Pi de 64 bits (arm64) – este é %s.
pt|ram_low|Só %s de RAM – o Emkay Home quer 2 GB ou mais (4 GB é melhor). A continuar.
pt|disk_low|Só %s livres – o Emkay Home quer cerca de 5 GB. A continuar.
pt|lxc|Isto é um contentor LXC.
pt|need_root|É preciso root: execute como root, ou instale o sudo.
pt|need_curl|É preciso o curl.
pt|docker_ok|O Docker está cá
pt|docker_install|A instalar o Docker
pt|docker_unknown|Não sei instalar o Docker em %s – instale o Docker (com “docker compose”) e execute isto de novo.
pt|docker_cant|O Docker não consegue iniciar contentores aqui.
pt|lxc_hint|No Proxmox: o contentor → Options → Features → ative “nesting” (e “keyctl” num contentor sem privilégios), reinicie-o e execute isto de novo.
pt|again|Já instalado em %s – a atualizar.
pt|ports|A casa: portas %s e %s
pt|ports_moved|A porta 80 ou 443 está ocupada – a casa usa %s e %s
pt|files|A transferir a configuração do Emkay Home
pt|pull|A transferir o OpenVoiceOS e o Emkay Home – da primeira vez demora alguns minutos
pt|build|A construir o Emkay Home nesta máquina – um minuto ou dois
pt|start|A iniciar a casa
pt|wait|À espera que a casa acorde
pt|wait_fail|A casa não respondeu a tempo.
pt|ready|O Emkay Home está a funcionar!
pt|updated|O Emkay Home está atualizado e a funcionar!
pt|open|Abra isto no seu PC ou telemóvel:
pt|scan|ou leia-o com o telemóvel:
pt|next|Aí escolhe o idioma e uma palavra-passe – e adiciona o seu primeiro Emkay.
pt|fail|Algo correu mal. As últimas linhas do registo (%s):
pt|un_ask|Apagar também os dados da casa – os Emkays emparelhados e o certificado? [s/N] 
pt|un_done|O Emkay Home foi removido.
pt|un_kept|Os dados ficam guardados – uma nova instalação recupera-os.
pt|status_up|O Emkay Home está a funcionar (%s de %s serviços).
pt|status_down|O Emkay Home não está a funcionar (%s de %s serviços) – inicie-o com: emkay-home start
pt|add_hint|Um telemóvel novo: abra o endereço e toque em “Adicionar um Emkay”.
pt|cmds|Mais: emkay-home update · logs · restart · uninstall
pt|later|Execute emkay-home para ver isto de novo.
pt-br|check|Olhando esta máquina
pt-br|ram_low|Só %s de RAM – o Emkay Home quer 2 GB ou mais (4 GB é melhor). Continuando.
pt-br|disk_low|Só %s livres – o Emkay Home quer cerca de 5 GB. Continuando.
pt-br|lxc|Isto é um contêiner LXC.
pt-br|need_root|Precisa de root: execute como root, ou instale o sudo.
pt-br|docker_ok|O Docker está aqui
pt-br|docker_install|Instalando o Docker
pt-br|docker_cant|O Docker não consegue iniciar contêineres aqui.
pt-br|lxc_hint|No Proxmox: o contêiner → Options → Features → ative “nesting” (e “keyctl” em um contêiner sem privilégios), reinicie-o e execute isto de novo.
pt-br|again|Já instalado em %s – atualizando.
pt-br|files|Baixando a configuração do Emkay Home
pt-br|pull|Baixando o OpenVoiceOS e o Emkay Home – da primeira vez leva alguns minutos
pt-br|build|Construindo o Emkay Home nesta máquina – um minuto ou dois
pt-br|start|Iniciando a casa
pt-br|wait|Esperando a casa acordar
pt-br|ready|O Emkay Home está funcionando!
pt-br|updated|O Emkay Home está atualizado e funcionando!
pt-br|open|Abra isto no seu PC ou celular:
pt-br|scan|ou escaneie com o celular:
pt-br|next|Lá você escolhe o idioma e uma senha – e adiciona o seu primeiro Emkay.
pt-br|fail|Algo deu errado. As últimas linhas do log (%s):
pt-br|un_ask|Apagar também os dados da casa – os Emkays pareados e o certificado? [s/N] 
pt-br|un_kept|Os dados ficam guardados – uma nova instalação os recupera.
pt-br|status_up|O Emkay Home está funcionando (%s de %s serviços).
pt-br|status_down|O Emkay Home não está funcionando (%s de %s serviços) – inicie com: emkay-home start
pt-br|add_hint|Um celular novo: abra o endereço e toque em “Adicionar um Emkay”.
pt-br|later|Execute emkay-home para ver isto de novo.
'

# The installer's language: --lang, then $LANG/$LC_ALL ("da_DK.UTF-8" → da).
# pt-br falls back to pt, then English; every other language to English.
pick_lang() {
  # the first of these that names a language (not "C" or "POSIX", which
  # containers and minimal systems often set)
  local l="" v
  for v in "$UI_LANG" "${LANGUAGE%%:*}" "$LC_ALL" "$LC_MESSAGES" "$LANG"; do
    case "$v" in ""|C|C.*|POSIX) ;; *) l="$v"; break ;; esac
  done
  l="$(printf '%s' "${l:-en}" | tr 'A-Z_' 'a-z-' | cut -d. -f1)"
  case "$l" in
    pt-br*) echo pt-br ;;
    da*|de*|es*|ca*|gl*|eu*|fr*|it*|nl*|pt*) echo "${l%%-*}" ;;
    *) echo en ;;
  esac
}
UI="$(pick_lang)"

# say KEY [values…] – the text in the installer's language (with fallbacks).
say() {
  local key="$1"; shift
  local text l
  for l in "$UI" "${UI%%-*}" en; do
    text="$(printf '%s\n' "$TEXTS" | awk -F'|' -v l="$l" -v k="$key" '$1==l && $2==k { sub(/^[^|]*\|[^|]*\|/, ""); print; exit }')"
    [ -n "$text" ] && break
  done
  # shellcheck disable=SC2059
  printf "$text" "$@"
}

ok()   { printf '  %s✓%s %s\n' "$C_OK" "$C_OFF" "$*"; }
note() { printf '  %s•%s %s\n' "$C_DIM" "$C_OFF" "$*"; }
warn() { printf '  %s!%s %s\n' "$C_WARN" "$C_OFF" "$*"; }
bad()  { printf '  %s✗%s %s\n' "$C_BAD" "$C_OFF" "$*"; }

# Stop with a message, and the end of the log when there is one.
die() {
  bad "$1"
  if [ -s "$LOG" ] && [ "${2:-}" != "nolog" ]; then
    printf '\n  %s%s%s\n' "$C_DIM" "$(say fail "$LOG")" "$C_OFF"
    tail -n 15 "$LOG" | sed "s/^/    /"
  fi
  printf '\n'
  exit 1
}

# step KEY command… – one line with a spinner while the command runs; its
# output goes to the log. ✓ when it succeeds; returns its exit code.
step() {
  local label; label="$(say "$1")"; shift
  printf '\n==> %s\n' "$label" >> "$LOG"
  if [ "$TTY" = 1 ]; then
    "$@" >> "$LOG" 2>&1 &
    # an array, not a string: substrings of multibyte characters break in a
    # machine without a UTF-8 locale (a fresh container)
    local pid=$! i=0 frames=(⠋ ⠙ ⠹ ⠸ ⠼ ⠴ ⠦ ⠧ ⠇ ⠏)
    printf '\e[?25l'   # hide the cursor while spinning
    while kill -0 "$pid" 2>/dev/null; do
      printf '\r  %s%s%s %s' "$C_ACCENT" "${frames[i++ % 10]}" "$C_OFF" "$label"
      sleep 0.1
    done
    wait "$pid"; local rc=$?
    printf '\r\e[K\e[?25h'
  else
    "$@" >> "$LOG" 2>&1; local rc=$?
  fi
  [ $rc -eq 0 ] && ok "$label"
  return $rc
}

banner() {
  local a="$C_ACCENT" o="$C_OFF"
  printf '\n'
  printf '  %s╭─────────╮%s\n' "$a" "$o"
  printf '  %s│  ◉   ◉  │%s    %sE M K A Y   H O M E%s\n' "$a" "$o" "$C_BOLD" "$o"
  printf '  %s│   ╰─╯   │%s    %s%s%s\n' "$a" "$o" "$C_DIM" "$(say tagline)" "$o"
  printf '  %s╰─────────╯%s\n\n' "$a" "$o"
}

# --- root ---------------------------------------------------------------------

SUDO=""
if [ "$(id -u)" -ne 0 ]; then
  command -v sudo >/dev/null 2>&1 || { banner; die "$(say need_root)" nolog; }
  SUDO="sudo"
fi
command -v curl >/dev/null 2>&1 || { banner; die "$(say need_curl)" nolog; }
: > "$LOG" 2>/dev/null || LOG="$HOME/emkay-home-install.log"
DC="$SUDO docker compose --project-directory $DIR/compose -f $DIR/compose/docker-compose.yml"

# --- uninstall ------------------------------------------------------------------

if [ "$UNINSTALL" = 1 ]; then
  banner
  answer=n
  # the script may come through a pipe: ask on the terminal itself
  if [ -r /dev/tty ]; then printf '  %s' "$(say un_ask)"; read -r answer < /dev/tty || answer=n; fi
  case "$answer" in
    [yYjJsSoObB]*) step un_done $DC down -v --remove-orphans ;;
    *) step un_done $DC down --remove-orphans; note "$(say un_kept)" ;;
  esac
  $SUDO rm -rf "$DIR"
  $SUDO rm -f /usr/local/bin/emkay-home
  printf '\n'; exit 0
fi

# --- the address ------------------------------------------------------------------

# Where the house is, for a person: its address (and name, with Avahi), and a
# QR code to open it on a phone – at the end of an install and in --status.
show_address() {
  local port_http ip port url
  port_http="$(sed -n 's/^HTTP_PORT=//p' "$DIR/compose/.env" 2>/dev/null)"; port_http="${port_http:-80}"
  ip="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{ for (i = 1; i < NF; i++) if ($i == "src") print $(i+1) }')"
  [ -z "$ip" ] && ip="$(hostname -I 2>/dev/null | awk '{ print $1 }')"
  port=""; [ "$port_http" != 80 ] && port=":$port_http"
  url="http://$ip$port/"
  printf '  %s\n\n' "$(say open)"
  printf '      %s%s%s\n' "$C_ACCENT$C_BOLD" "$url" "$C_OFF"
  # the machine's own name, when Avahi announces it on the network
  if systemctl is-active --quiet avahi-daemon 2>/dev/null; then
    printf '      %s%s%s\n' "$C_ACCENT" "http://$(hostname).local$port/" "$C_OFF"
  fi
  # a QR code for the phone, drawn by emkay_home's own segno (nothing to install)
  if [ "$TTY" = 1 ]; then
    printf '\n  %s\n' "$(say scan)"
    $SUDO docker exec emkay_home python -c \
      'import sys, segno; segno.make(sys.argv[1], error="l").terminal(compact=True, border=2)' "$url" 2>/dev/null \
      | sed 's/^/    /'
  fi
}

# --- status (emkay-home) ------------------------------------------------------------

if [ "$STATUS" = 1 ]; then
  banner
  total="$($DC config --services 2>/dev/null | wc -l)"
  up="$($DC ps --services --status running 2>/dev/null | wc -l)"
  if [ "$total" -gt 0 ] && [ "$up" -eq "$total" ]; then
    ok "$(say status_up "$up" "$total")"
    printf '\n'
    show_address
    printf '\n  %s\n' "$(say add_hint)"
  else
    warn "$(say status_down "$up" "$total")"
  fi
  printf '  %s%s%s\n\n' "$C_DIM" "$(say cmds)" "$C_OFF"
  exit 0
fi

# --- the machine ----------------------------------------------------------------

banner
printf '  %s\n\n' "$(say hello)"

. /etc/os-release 2>/dev/null
OS_NAME="${PRETTY_NAME:-Linux}"
ARCH="$(uname -m)"
RAM_MB="$(awk '/MemTotal/ { print int($2/1024) }' /proc/meminfo)"
mkdir -p "$DIR" 2>/dev/null || $SUDO mkdir -p "$DIR"
DISK_MB="$(df -Pm "$DIR" | awk 'NR==2 { print $4 }')"
VIRT="$(systemd-detect-virt 2>/dev/null || true)"
[ -z "$VIRT" ] && grep -qa 'container=lxc' /proc/1/environ 2>/dev/null && VIRT=lxc
human() { awk -v m="$1" 'BEGIN { if (m >= 1024) printf "%.1f GB", m/1024; else printf "%d MB", m }'; }

ok "$(say sys "$OS_NAME" "$ARCH" "$(human "$RAM_MB")" "$(human "$DISK_MB")")"
case "$ARCH" in
  x86_64|amd64|aarch64|arm64) ;;
  *) die "$(say arch_bad "$ARCH")" nolog ;;
esac
[ "$RAM_MB" -lt 1800 ] && warn "$(say ram_low "$(human "$RAM_MB")")"
[ "$DISK_MB" -lt 5000 ] && warn "$(say disk_low "$(human "$DISK_MB")")"
[ "$VIRT" = lxc ] && note "$(say lxc)"

# --- Docker ---------------------------------------------------------------------

# Per distribution family. get.docker.com (Docker's own script) where it is
# supported; the distribution's packages elsewhere.
#
# The families (what CI tests is in .github/workflows/distros.yml):
#   debian, ubuntu, raspbian, fedora, centos, rhel  get.docker.com
#   rocky, almalinux (and other RHEL rebuilds)      Docker's CentOS repository
#   linuxmint, pop, … (ID_LIKE ubuntu/debian)        the distribution's docker.io
#   arch, manjaro, endeavouros (ID_LIKE arch)        pacman
#   opensuse-*, sles                                 zypper
#   alpine                                           apk + OpenRC
docker_family() {
  case "${ID:-}" in
    debian|ubuntu|raspbian|fedora|centos|rhel) echo getdocker ;;
    rocky|almalinux|ol|centos-stream) echo rhel-repo ;;
    arch|manjaro|endeavouros|garuda|cachyos) echo pacman ;;
    alpine) echo apk ;;
    opensuse*|sles|sled) echo zypper ;;
    *) case " ${ID_LIKE:-} " in
         *" arch "*) echo pacman ;;
         *" rhel "*|*" centos "*) echo rhel-repo ;;
         *" fedora "*) echo getdocker ;;
         *" ubuntu "*|*" debian "*) echo apt ;;
         *suse*) echo zypper ;;
         *) echo unknown ;;
       esac ;;
  esac
}

install_docker() {
  case "$(docker_family)" in
    getdocker) curl -fsSL https://get.docker.com | $SUDO sh || return 1 ;;
    rhel-repo)
      $SUDO dnf -y install dnf-plugins-core \
        && $SUDO dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo \
        && $SUDO dnf -y install docker-ce docker-ce-cli containerd.io docker-compose-plugin || return 1 ;;
    apt)   # Mint, Pop!_OS, …: the distribution's own packages
      $SUDO apt-get update && { $SUDO apt-get install -y docker.io docker-compose-v2 \
        || $SUDO apt-get install -y docker.io docker-compose-plugin; } || return 1 ;;
    pacman) $SUDO pacman -Sy --noconfirm --needed docker docker-compose || return 1 ;;
    zypper) $SUDO zypper -n install docker docker-compose || return 1 ;;
    apk)
      $SUDO apk add docker docker-cli-compose && $SUDO rc-update add docker default \
        && $SUDO rc-service docker start || return 1
      return 0 ;;
    *) return 3 ;;
  esac
  # systemd only where it is running (not in every container); else the
  # init script, as in a minimal LXC
  if [ -d /run/systemd/system ]; then $SUDO systemctl enable --now docker
  else $SUDO service docker start; fi
}

# A freshly started Docker takes a moment before it answers (OpenRC returns
# before the daemon is up) – wait for it, up to a minute.
wait_docker() {
  local i
  for i in $(seq 1 30); do
    $SUDO docker info > /dev/null 2>&1 && return 0
    sleep 2
  done
  return 1
}

if command -v docker >/dev/null 2>&1 && $SUDO docker compose version >/dev/null 2>&1; then
  ok "$(say docker_ok)"
else
  step docker_install install_docker
  rc=$?
  [ $rc -eq 3 ] && die "$(say docker_unknown "$OS_NAME")" nolog
  [ $rc -ne 0 ] && die "$(say docker_install)"
fi
wait_docker >> "$LOG" 2>&1

# Can Docker start a container here? (In an LXC container without "nesting"
# it can't.) Caddy is needed anyway, so this costs nothing extra.
if ! $SUDO docker run --rm docker.io/library/caddy:2 caddy version >> "$LOG" 2>&1; then
  [ "$VIRT" = lxc ] && die "$(say docker_cant) $(say lxc_hint)"
  die "$(say docker_cant)"
fi

# --- ports ----------------------------------------------------------------------

port_free() { ! (ss -ltnH 2>/dev/null || netstat -ltn 2>/dev/null) | awk '{ print $4 }' | grep -qE "[:.]$1\$"; }

UPDATE=0
[ -f "$DIR/compose/.env" ] && UPDATE=1
if [ "$UPDATE" = 1 ]; then
  note "$(say again "$DIR")"
  # keep the ports the house already has (its QR codes and phones use them)
  HTTP_PORT="${HTTP_PORT:-$(sed -n 's/^HTTP_PORT=//p' "$DIR/compose/.env")}"
  HTTPS_PORT="${HTTPS_PORT:-$(sed -n 's/^HTTPS_PORT=//p' "$DIR/compose/.env")}"
  ok "$(say ports "$HTTP_PORT" "$HTTPS_PORT")"
elif [ -z "$HTTP_PORT$HTTPS_PORT" ]; then
  if port_free 80 && port_free 443; then
    HTTP_PORT=80; HTTPS_PORT=443
    ok "$(say ports 80 443)"
  else
    HTTP_PORT=8080; HTTPS_PORT=8443
    warn "$(say ports_moved 8080 8443)"
  fi
else
  HTTP_PORT="${HTTP_PORT:-80}"; HTTPS_PORT="${HTTPS_PORT:-443}"
  ok "$(say ports "$HTTP_PORT" "$HTTPS_PORT")"
fi

# --- the setup ------------------------------------------------------------------

host_tz() {
  timedatectl show -p Timezone --value 2>/dev/null \
    || cat /etc/timezone 2>/dev/null \
    || readlink /etc/localtime 2>/dev/null | sed 's|.*/zoneinfo/||' \
    || echo UTC
}

fetch_setup() {
  $SUDO mkdir -p "$DIR/compose" "$DIR/caddy" || return 1
  local f
  for f in compose/docker-compose.yml compose/.env.example caddy/Caddyfile; do
    curl -fsSL "$RAW/$REF/$f" | $SUDO tee "$DIR/$f.new" > /dev/null || return 1
    $SUDO mv "$DIR/$f.new" "$DIR/$f"
  done
  # the `emkay-home` command, and the installer it runs for its texts
  $SUDO mkdir -p "$DIR/bin" || return 1
  for f in home.sh emkay-home; do
    curl -fsSL "$RAW/$REF/install/$f" | $SUDO tee "$DIR/bin/$f.new" > /dev/null || return 1
    $SUDO mv "$DIR/bin/$f.new" "$DIR/bin/$f"
  done
  sed "s|@DIR@|$DIR|" "$DIR/bin/emkay-home" | $SUDO tee /usr/local/bin/emkay-home > /dev/null \
    && $SUDO chmod 755 /usr/local/bin/emkay-home
  # .env is the house's own: written once, kept on updates
  if [ ! -f "$DIR/compose/.env" ]; then
    sed -e "s|^TZ=.*|TZ=$(host_tz)|" -e "s|^HTTP_PORT=.*|HTTP_PORT=$HTTP_PORT|" \
        -e "s|^HTTPS_PORT=.*|HTTPS_PORT=$HTTPS_PORT|" "$DIR/compose/.env.example" \
      | $SUDO tee "$DIR/compose/.env" > /dev/null
  fi
}

step files fetch_setup || die "$(say files)"
# Emkay Home's own image comes from ghcr.io; when it can't be pulled (not
# published for this architecture, not public, no access to ghcr.io), the
# installer builds it here from the same source – so the one line works
# whatever happens to the image. EMKAY_HOME_BUILD=1 always builds.
EH_IMAGE="ghcr.io/emkay-voice/emkay-home:$(sed -n 's/^EMKAY_HOME_VERSION=//p' "$DIR/compose/.env" 2>/dev/null)"
[ "$EH_IMAGE" = "ghcr.io/emkay-voice/emkay-home:" ] && EH_IMAGE="ghcr.io/emkay-voice/emkay-home:latest"

build_emkay_home() {
  $SUDO rm -rf "$DIR/src" && $SUDO mkdir -p "$DIR/src" || return 1
  curl -fsSL "https://codeload.github.com/emkay-voice/emkay-home/tar.gz/$REF" \
    | $SUDO tar -xz -C "$DIR/src" --strip-components=1 || return 1
  $SUDO docker build -f "$DIR/src/image/Dockerfile" -t "$EH_IMAGE" "$DIR/src"
}

step pull $DC pull --ignore-pull-failures || die "$(say pull)"
if [ "${EMKAY_HOME_BUILD:-0}" = 1 ] || ! $SUDO docker image inspect "$EH_IMAGE" > /dev/null 2>&1; then
  step build build_emkay_home || die "$(say build)"
fi
step start $DC up -d --no-build --remove-orphans || die "$(say start)"

# The house is up when Caddy serves its certificate and the page answers.
wait_house() {
  local i
  for i in $(seq 1 150); do
    curl -fsS "http://127.0.0.1:$HTTP_PORT/ca.crt" > /dev/null 2>&1 \
      && curl -fsS "http://127.0.0.1:$HTTP_PORT/api/info" > /dev/null 2>&1 && return 0
    sleep 2
  done
  return 1
}
step wait wait_house || die "$(say wait_fail)"

# --- done -----------------------------------------------------------------------

printf '\n  %s%s%s\n\n' "$C_BOLD" "$(say "$([ "$UPDATE" = 1 ] && echo updated || echo ready)")" "$C_OFF"
show_address
printf '\n  %s%s%s\n' "$C_DIM" "$(say next)" "$C_OFF"
printf '  %s%s%s\n\n' "$C_DIM" "$(say later)" "$C_OFF"
