"""Constanten voor de YouTube Tracker integratie."""

from __future__ import annotations

DOMAIN = "youtube_tracker"

# --- Configuratiesleutels ---------------------------------------------------
CONF_CHANNEL_ID = "channel_id"
CONF_CHANNEL_NAME = "channel_name"
CONF_LOOKBACK_MODE = "lookback_mode"
CONF_LOOKBACK_DAYS = "lookback_days"
CONF_SCAN_INTERVAL = "scan_interval"

# --- Terugkijk-modi ---------------------------------------------------------
# "vorige_maand" = alles vanaf de 1e dag van de vorige kalendermaand
# "dagen"        = alles binnen het opgegeven aantal dagen
MODE_VORIGE_MAAND = "vorige_maand"
MODE_DAGEN = "dagen"
DEFAULT_LOOKBACK_MODE = MODE_VORIGE_MAAND
DEFAULT_LOOKBACK_DAYS = 30
MIN_LOOKBACK_DAYS = 1
MAX_LOOKBACK_DAYS = 365

# --- Verversing (minuten) ---------------------------------------------------
DEFAULT_SCAN_INTERVAL = 30
MIN_SCAN_INTERVAL = 10
MAX_SCAN_INTERVAL = 1440

# --- Opslag van bekeken video's --------------------------------------------
STORAGE_KEY = f"{DOMAIN}.watched"
STORAGE_VERSION = 1
# Bekeken video's ouder dan dit aantal dagen worden automatisch opgeruimd.
# Bewust ruimer dan MAX_LOOKBACK_DAYS: anders wordt een markering opgeruimd
# terwijl de video nog binnen de peildatum valt, en verschijnt hij opnieuw
# als "ongezien".
WATCHED_RETENTION_DAYS = MAX_LOOKBACK_DAYS + 35
# Hoe vaak de opschoning draait zolang Home Assistant aan staat
PURGE_INTERVAL_HOURS = 24

# --- Archief van gevonden video's -------------------------------------------
# De feed van YouTube toont maar ongeveer 15 video's per kanaal. Alles wat we
# ooit in die feed hebben zien staan bewaren we zelf, zodat een video niet uit
# je lijst verdwijnt voordat je hem hebt afgevinkt.
ARCHIVE_STORAGE_KEY = f"{DOMAIN}.videos"
# Gelijk aan de bewaartermijn van de markeringen: anders bewaar je een
# markering voor een video die je niet meer kent, of andersom
ARCHIVE_RETENTION_DAYS = WATCHED_RETENTION_DAYS
# Harde bovengrens per kanaal, als verzekering tegen een kanaal dat extreem
# veel uploadt. Bij overschrijding vallen de oudste video's af.
MAX_ARCHIVE_PER_CHANNEL = 1000

# --- Services ---------------------------------------------------------------
SERVICE_MARK_WATCHED = "mark_watched"
SERVICE_MARK_UNWATCHED = "mark_unwatched"
SERVICE_MARK_ALL_WATCHED = "mark_all_watched"

ATTR_VIDEO_ID = "video_id"
ATTR_URL = "url"
ATTR_ENTITY_ID = "entity_id"

# --- Events en signalen -----------------------------------------------------
# Wordt afgevuurd zodra er een nieuwe, nog ongeziene video verschijnt
EVENT_NIEUWE_VIDEO = f"{DOMAIN}_nieuwe_video"
# Interne dispatcher: alle sensors herberekenen na een wijziging in de opslag
SIGNAL_WATCHED_UPDATED = f"{DOMAIN}_watched_updated"

# --- YouTube endpoints ------------------------------------------------------
# Let op: de UULF-prefix (channel-ID met UC vervangen door UULF) levert de
# "long form uploads"-playlist, oftewel de feed zonder Shorts.
FEED_URL = "https://www.youtube.com/feeds/videos.xml?playlist_id=UULF{}"
# Fallback wanneer de UULF-playlist geen resultaat geeft
FEED_URL_FALLBACK = "https://www.youtube.com/feeds/videos.xml?channel_id={}"
# Kanaalpagina, gebruikt om een @handle om te zetten naar een channel-ID
CHANNEL_PAGE_URL = "https://www.youtube.com/{}"

VIDEO_URL = "https://www.youtube.com/watch?v={}"
THUMBNAIL_URL = "https://i.ytimg.com/vi/{}/hqdefault.jpg"

# Hosts die we accepteren als iemand een volledige URL invult. Zonder deze
# controle zou Home Assistant een verzoek doen naar elk adres dat je intypt.
TOEGESTANE_HOSTS = frozenset(
    {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}
)

# XML-namespaces van de YouTube Atom-feed
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
    "media": "http://search.yahoo.com/mrss/",
}

# Maximaal aantal video's dat in het sensor-attribuut wordt gezet. De teller
# zelf telt altijd alles; dit begrenst alleen de lijst op je dashboard.
MAX_VIDEOS_IN_ATTRIBUTE = 50

# --- Redirect-view ----------------------------------------------------------
# Pad van de "markeer en open"-link. De handtekening wordt per video berekend
# uit het geheim in de opslag, zodat het geheim zelf nooit in een attribuut
# terechtkomt. Zie WatchedStore.maak_handtekening.
VIEW_URL = "/api/youtube_tracker/{video_id}/{signature}"
# Dezelfde link, maar dan alleen afvinken zonder de video te openen. Het
# antwoord is een lege 204, waardoor je browser op je dashboard blijft staan.
MARK_URL = VIEW_URL + "?open=0"
QUERY_OPEN = "open"
STORAGE_SECRET_KEY = "secret"
# Lengte van de handtekening in de URL. 22 tekens base64 ~= 132 bits, ruim
# genoeg om niet te raden en kort genoeg voor een nette URL.
SIGNATURE_LENGTH = 22
