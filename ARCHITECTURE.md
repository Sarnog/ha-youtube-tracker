🇳🇱 [Nederlands](#architectuur) | 🇬🇧 [English](#architecture)

---

# Architectuur

## Overzicht

Het project is opgedeeld in lagen. Elke laag heeft precies één
verantwoordelijkheid en kent alleen de laag eronder.

```
Internet (YouTube)
    │
    ▼
feed.py ─────────── haalt de Atom-feed op en leest hem uit
    │
    ▼
archive.py ──────── bewaart alles wat we ooit in de feed zagen
    │               (de feed zelf toont er maar vijftien)
    ▼
coordinator.py ──── een per kanaal: verversen, peildatum, events
    │
    ▼
sensor.py ───────── de teller en de videolijst
    │
    ▼
Je dashboard
    │
    │ klik op kijk_url of markeer_url
    ▼
view.py ─────────── markeert de video, en opent hem eventueel
    │
    ▼
store.py ────────── de bekeken-lijst en de handtekeningen
```

`store.py` staat onderaan de klikketen, maar wordt ook door `coordinator.py`
en `sensor.py` geraadpleegd: die moeten weten wat al bekeken is. Het is de
enige laag die door meerdere andere lagen wordt gebruikt.

---

# const.py

Alle vaste waarden op één plek: URL's, sleutels voor de opslag, standaard- en
grenswaarden, namen van services en events.

Geen logica. Geen Home Assistant-code.

Wie een grens wil verleggen, hoeft alleen hier te zijn.

---

# feed.py

Uitsluitend verantwoordelijk voor het ophalen en uitlezen van de publieke
Atom-feed van YouTube.

Kent geen Home Assistant, op de datumhulpjes na. Kent geen opslag en geen
sensors. Levert gewone dictionaries af.

Twee taken:

- `async_resolve_channel_id` zet gebruikersinvoer om naar een channel-ID. Een
  kaal `UC...`-ID kost geen verzoek; een `@handle` of URL wordt op de
  kanaalpagina opgezocht. URL's buiten YouTube worden geweigerd.
- `async_fetch_feed` haalt eerst de `UULF`-playlist op, want die bevat geen
  Shorts, en valt terug op de gewone kanaalfeed als dat niets oplevert.

Een feed die goed binnenkomt maar leeg is, is geen fout: dat is een kanaal dat
nog niets heeft geüpload.

---

# archive.py

Bewaart per kanaal elke video die ooit in de feed stond.

Dit is de kern van de integratie. De feed van YouTube is een **venster** van
ongeveer vijftien video's, geen archief: zodra er een zestiende bijkomt, valt
de oudste eruit. Zonder deze laag zou een video die je nog niet had afgevinkt
gewoon uit je lijst verdwijnen.

Het venster van YouTube schuift op, ons archief niet. Een video verdwijnt pas
als jij hem afvinkt, of als hij zo oud is dat hij nooit meer kan meetellen.

Het archief bepaalt ook wat "nieuw" is. Omdat het op schijf staat, telt een
herstart niet als eerste ronde: video's die verschenen terwijl Home Assistant
uit stond leveren gewoon een event op. Alleen een kanaal dat we nog helemaal
niet kennen wordt stil gevuld, anders krijg je vijftien meldingen ineens.

Dit werkt alleen vooruit. Wat al uit de feed was voordat je het kanaal
toevoegde, is niet meer op te halen.

---

# store.py

De lijst met bekeken video's, en het geheim waarmee de klik-links worden
ondertekend.

Gedeeld door alle kanalen: een video-ID is uniek op heel YouTube, dus het
heeft geen zin dit per kanaal bij te houden.

Twee verantwoordelijkheden die bewust bij elkaar staan, omdat ze allebei in
hetzelfde bestand in `.storage` leven:

- markeren, terugdraaien en opruimen van bekeken video's
- handtekeningen maken en controleren

Na elke wijziging gaat er een signaal naar de sensors, zodat die hun waarde
opnieuw berekenen zonder op de volgende verversing te wachten.

---

# coordinator.py

Eén coordinator per kanaal, bovenop de `DataUpdateCoordinator` van Home
Assistant.

Verzorgt het periodiek ophalen, vult het archief aan en vuurt events af voor
nieuwe video's. Geeft niet de feed terug maar het volledige archief van dat
kanaal.

Hier woont ook de peildatum. Die wordt berekend in de tijdzone van jouw Home
Assistant, niet in UTC: "begin van de vorige maand" hoort middernacht bij jou
te zijn. In UTC zou de maand voor ons pas om 01:00 of 02:00 beginnen, en
vielen video's uit dat gaatje er net buiten.

---

# sensor.py

Eén sensor per kanaal. De waarde is het aantal ongeziene video's binnen de
peildatum; de video's zelf staan in het attribuut `videos`.

De waarde wordt live uit de coordinator en de opslag berekend, niet
tussentijds bewaard. Daardoor is één `async_write_ha_state()` genoeg om alles
bij te werken nadat er iets is afgevinkt.

Het attribuut `videos` staat in `_unrecorded_attributes`. De lijst is groot en
verandert vaak; zonder dat zou hij bij elke wijziging opnieuw in de
recorder-database belanden. De teller zelf blijft gewoon in je historie staan.

De teller telt alle ongeziene video's, de lijst is afgekapt op vijftig.

---

# view.py

Het HTTP-endpoint achter de twee klik-links.

Markeert de video als bekeken en stuurt je daarna door naar YouTube, of
antwoordt met een lege `204` zodat je browser blijft staan waar hij staat.

Vereist bewust geen login: anders zou de link niet werken vanuit een
notificatie of een browser waarin je niet bent ingelogd. In plaats daarvan zit
er per video een handtekening in de URL.

---

# De links en hun handtekening

Een sensor-attribuut is niet geheim. Het is leesbaar voor elke gebruiker van
Home Assistant, het belandt in de database en het gaat mee in elk screenshot
of diagnosebestand dat je deelt.

Daarom staat het geheim er niet in. In plaats daarvan wordt per video een
HMAC berekend uit het geheim en het video-ID. Het geheim blijft in `.storage`
en verlaat Home Assistant nooit.

Het gevolg: wie een link onderschept, kan daarmee alleen die ene video
afvinken. Niet je hele lijst, en niet de video's van volgende week. Eén vast
token voor alles zou dat wel toestaan.

Erger dan afvinken kan het niet worden: er loopt geen weg van dit endpoint
naar de rest van Home Assistant.

---

# config_flow.py

De schermen voor het toevoegen van een kanaal en het aanpassen van de
instellingen.

Controleert bij het toevoegen meteen of de feed werkelijk werkt, zodat je een
typefout direct ziet in plaats van pas bij de eerste verversing.

Het channel-ID is de unieke sleutel, dus hetzelfde kanaal twee keer toevoegen
wordt geweigerd, ook als je de ene keer een handle en de andere keer een URL
gebruikt.

---

# __init__.py

Zet de integratie op en registreert de services.

Alles wat door alle kanalen wordt gedeeld — de opslag, het archief, de view en
de services — wordt aangemaakt in `async_setup`, niet per kanaal. Dat is geen
smaakkwestie: Home Assistant zet de kanalen **parallel** op, dus twee kanalen
zouden tegelijk kunnen besluiten dat de opslag nog niet bestaat.

`async_setup` draait gegarandeerd één keer, vóór alle kanalen.

---

# Opslag

Twee losse bestanden in `.storage`, met verschillende levensduur en omvang:

| Bestand | Inhoud |
| --- | --- |
| `youtube_tracker.watched` | Bekeken video-ID's met het moment van afvinken, plus het geheim |
| `youtube_tracker.videos` | Het archief van gevonden video's, per kanaal |

Beide worden dagelijks opgeruimd. De bewaartermijnen zijn expres gelijk: zou
een markering eerder verdwijnen dan de video, dan zou die video opnieuw als
ongezien opduiken.

Er wordt alleen naar schijf geschreven als er echt iets is veranderd. Een
verversing zonder nieuwe video's raakt de opslag niet aan.

---

# Async

Alles draait in de event loop van Home Assistant. Er wordt niets geblokkeerd:
de netwerkverzoeken lopen via de gedeelde `aiohttp`-sessie en de opslag via de
`Store` van Home Assistant.

---

# Uitbreidbaarheid

De lagen zijn zo gekozen dat een uitbreiding meestal in één bestand past:

- Een ander veld uit de feed? `feed.py`, en daarna doorgeven in `archive.py`.
- Shorts wel meetellen? Een andere URL in `const.py` en een keuze in
  `config_flow.py`.
- Een tweede entiteit per kanaal? Een nieuw platform naast `sensor.py`; de
  coordinator hoeft niet te veranderen.
- Een andere manier van afvinken? `view.py` of een extra service; de rest merkt
  er niets van, want alles loopt via `store.py`.


---



# Architecture

## Overview

The project is split into layers. Each layer has exactly one responsibility
and only knows about the layer below it.

```
Internet (YouTube)
    │
    ▼
feed.py ─────────── fetches the Atom feed and reads it
    │
    ▼
archive.py ──────── keeps everything we ever saw in the feed
    │               (the feed itself only shows about fifteen)
    ▼
coordinator.py ──── one per channel: refreshing, cut-off date, events
    │
    ▼
sensor.py ───────── the counter and the video list
    │
    ▼
Your dashboard
    │
    │ click on kijk_url or markeer_url
    ▼
view.py ─────────── marks the video, and opens it if asked
    │
    ▼
store.py ────────── the watched list and the signatures
```

`store.py` sits at the bottom of the click chain, but `coordinator.py` and
`sensor.py` consult it too: they need to know what has already been watched.
It is the only layer used by more than one other layer.

---

# const.py

Every fixed value in one place: URLs, storage keys, defaults and limits, names
of services and events.

No logic. No Home Assistant code.

Anyone wanting to move a limit only has to be here.

---

# feed.py

Solely responsible for fetching and reading YouTube's public Atom feed.

Knows nothing about Home Assistant beyond the date helpers. Knows nothing
about storage or sensors. Hands back plain dictionaries.

Two jobs:

- `async_resolve_channel_id` turns user input into a channel ID. A bare
  `UC...` ID costs no request; an `@handle` or URL is looked up on the channel
  page. URLs outside YouTube are refused.
- `async_fetch_feed` first fetches the `UULF` playlist, because it holds no
  Shorts, and falls back to the regular channel feed if that yields nothing.

A feed that arrives fine but is empty is not an error: that is a channel that
has not uploaded anything yet.

---

# archive.py

Keeps every video that ever appeared in the feed, per channel.

This is the heart of the integration. YouTube's feed is a **window** of about
fifteen videos, not an archive: as soon as a sixteenth arrives, the oldest
drops out. Without this layer a video you had not cleared yet would simply
vanish from your list.

YouTube's window moves on, our archive does not. A video only disappears once
you clear it, or once it is so old it can never count again.

The archive also decides what counts as "new". Because it lives on disk, a
restart does not count as a first round: videos that appeared while Home
Assistant was down still produce an event. Only a channel we do not know at
all is filled silently, otherwise you would get fifteen notifications at once.

This only works going forward. Whatever had already left the feed before you
added the channel is out of reach.

---

# store.py

The list of watched videos, and the secret used to sign the click links.

Shared by all channels: a video ID is unique across all of YouTube, so there
is no point keeping this per channel.

Two responsibilities that deliberately sit together, because both live in the
same file under `.storage`:

- marking, undoing and cleaning up watched videos
- creating and verifying signatures

After every change a signal goes out to the sensors, so they recalculate their
value without waiting for the next refresh.

---

# coordinator.py

One coordinator per channel, on top of Home Assistant's
`DataUpdateCoordinator`.

Handles periodic fetching, tops up the archive and fires events for new
videos. Returns not the feed but that channel's complete archive.

The cut-off date lives here too. It is calculated in your Home Assistant's
time zone, not in UTC: "the start of last month" should be midnight where you
are. In UTC the month would only start at 01:00 or 02:00 for us, and videos
from that gap fell just outside it.

---

# sensor.py

One sensor per channel. Its value is the number of unwatched videos within the
cut-off date; the videos themselves live in the `videos` attribute.

The value is computed live from the coordinator and the storage, not cached in
between. That makes a single `async_write_ha_state()` enough to update
everything after something has been cleared.

The `videos` attribute is listed in `_unrecorded_attributes`. The list is
large and changes often; without that it would land in the recorder database
on every change. The counter itself stays in your history as usual.

The counter counts every unwatched video, the list is capped at fifty.

---

# view.py

The HTTP endpoint behind the two click links.

Marks the video as watched and then redirects you to YouTube, or replies with
an empty `204` so your browser stays where it is.

Deliberately requires no login: otherwise the link would not work from a
notification or from a browser you are not signed in to. Instead, the URL
carries a per-video signature.

---

# The links and their signature

A sensor attribute is not secret. It is readable by every Home Assistant user,
it lands in the database, and it travels along in every screenshot or
diagnostics file you share.

So the secret is not in there. Instead, an HMAC is computed per video from the
secret and the video ID. The secret stays in `.storage` and never leaves Home
Assistant.

The result: anyone intercepting a link can only clear that one video. Not your
whole list, and not next week's videos. A single fixed token for everything
would allow exactly that.

It cannot get worse than clearing: there is no path from this endpoint into
the rest of Home Assistant.

---

# config_flow.py

The screens for adding a channel and changing its settings.

While adding, it immediately checks whether the feed actually works, so you
see a typo right away instead of at the first refresh.

The channel ID is the unique key, so adding the same channel twice is refused,
even if you use a handle one time and a URL the next.

---

# __init__.py

Sets up the integration and registers the services.

Everything shared by all channels — the storage, the archive, the view and the
services — is created in `async_setup`, not per channel. That is not a matter
of taste: Home Assistant sets the channels up **in parallel**, so two channels
could decide at the same time that the storage does not exist yet.

`async_setup` is guaranteed to run once, before any channel.

---

# Storage

Two separate files under `.storage`, with different lifetimes and sizes:

| File | Contents |
| --- | --- |
| `youtube_tracker.watched` | Watched video IDs with the moment they were cleared, plus the secret |
| `youtube_tracker.videos` | The archive of found videos, per channel |

Both are cleaned up daily. The retention periods are equal on purpose: if a
marking disappeared before the video did, that video would resurface as
unwatched.

Writing to disk only happens when something actually changed. A refresh
without new videos leaves the storage untouched.

---

# Async

Everything runs in Home Assistant's event loop. Nothing blocks: network
requests go through the shared `aiohttp` session and storage through Home
Assistant's `Store`.

---

# Extensibility

The layers are cut so that an addition usually fits in a single file:

- Another field from the feed? `feed.py`, then pass it along in `archive.py`.
- Include Shorts after all? A different URL in `const.py` and a choice in
  `config_flow.py`.
- A second entity per channel? A new platform next to `sensor.py`; the
  coordinator does not have to change.
- A different way of clearing? `view.py` or an extra service; nothing else
  notices, because everything goes through `store.py`.
