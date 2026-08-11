  <a href="#nl">NL</a> | <a href="#en">EN</a>

<div align="center">
  <!-- align="center" centreert alles binnen deze div -->
  <h1>
    <!-- h1 = grootste kop, standaard al dikgedrukt en groot -->
    <ins>YouTube Tracker</ins>
    <!-- ins = onderstreepte tekst op GitHub -->
  </h1>
</div>


##### <ins>NL</ins>

Houdt per YouTube-kanaal bij hoeveel video's je nog niet bekeken hebt, met een lijst
van die video's als attribuut zodat je ze direct op je dashboard kunt zetten.

<table>
  <tr>
    <td>Integratie toevoegen:</td>
    <td><a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=Sarnog&amp;repository=ha-youtube-tracker&amp;category=integration"><img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="Open your Home Assistant instance and open a repository inside the Home Assistant Community Store."></a></td>
  </tr>
</table>

**Te installeren via HACS als custom repository, of handmatig - zie [Installatie](#installatie).**

### Wat doet dit

Je voegt per kanaal een integratie-entry toe. Elk kanaal krijgt een sensor waarvan de
waarde het aantal ongeziene video's is, met de video's zelf als attribuut.

- Databron is de publieke RSS-feed van YouTube: geen API-key, geen quota
- Gebruikt de `UULF`-playlist, dus **zonder Shorts**
- Attribuut `videos` bevat titel, URL, thumbnail, publicatiedatum en twee klik-links
- Bekeken video's worden persistent opgeslagen en overleven een herstart
- Eén klik markeert een video als bekeken, met of zonder hem te openen

**Meer dan vijftien video's.** YouTube toont in de feed maar zo'n vijftien video's per
kanaal. Dat is een venster, geen archief: video nummer zestien verdwijnt eruit. Deze
integratie schrijft daarom bij elke ronde op wat ze ziet en bewaart dat zelf. Het
venster van YouTube schuift op, jouw lijst niet - een video verdwijnt pas als jij hem
afvinkt.

Vereist Home Assistant **2025.6.0** of nieuwer.

### Installatie

**Via HACS** (aanbevolen): klik de HACS-badge bovenaan dit bestand, of voeg deze
repository handmatig toe als **custom repository** in HACS (HACS > drie puntjes >
Aangepaste repositories > deze GitHub-URL, categorie "Integratie").

**Handmatig**, als alternatief:

1. Kopieer de map `custom_components/youtube_tracker` naar de `custom_components`-map
   van je Home Assistant-configuratie.
2. Herstart Home Assistant.

Voeg daarna kanalen toe via **Instellingen > Apparaten & diensten > Integratie
toevoegen > YouTube Tracker**. Je kunt een channel-ID (`UC...`), een `@handle` of een
volledige kanaal-URL invullen.

### Instellingen per kanaal

| Optie | Standaard | Uitleg |
| --- | --- | --- |
| Tel video's mee vanaf | Begin vorige maand | Peildatum, rollend per maand |
| Aantal dagen terug | 30 | Alleen bij modus "aantal dagen", maximaal 365 |
| Verversen elke | 30 minuten | Minimaal 10 minuten |

De peildatum wordt berekend in de tijdzone van je Home Assistant, dus "begin van de
vorige maand" is echt middernacht bij jou en niet in UTC.

### Services

| Service | Uitleg |
| --- | --- |
| `youtube_tracker.mark_watched` | Markeer één video (`video_id` of `url`) |
| `youtube_tracker.mark_unwatched` | Zet één video terug op ongezien |
| `youtube_tracker.mark_all_watched` | Vink alles af, optioneel per sensor via `entity_id` |

### Op je dashboard

Elke video in het `videos`-attribuut heeft twee links:

| Link | Wat hij doet |
| --- | --- |
| `kijk_url` | Markeert de video als bekeken **en** opent hem op YouTube |
| `markeer_url` | Vinkt de video alleen af; je blijft op je dashboard |

Die tweede is handig als je een video buiten Home Assistant om al hebt gezien. Hij
antwoordt met een lege HTTP 204, waardoor je browser niet wegnavigeert. De sensor
verandert, dus de kaart werkt zichzelf bij.

Een voorbeeld met een markdown-card:

```yaml
type: markdown
content: |
  {% for video in state_attr('sensor.youtube_kanaalnaam', 'videos') %}
  [![]({{ video.thumbnail }})]({{ video.kijk_url }})

  **[{{ video.titel }}]({{ video.kijk_url }})** - [afvinken]({{ video.markeer_url }})
  {% endfor %}
```

Beide links werken zonder login, want anders zouden ze niet werken vanuit een
notificatie. In plaats van een wachtwoord zit er per video een handtekening in de URL,
die alleen jouw Home Assistant kan maken. Een onderschepte link geldt dus alleen voor
die ene video, nooit voor je hele lijst.

### Event

Bij een nieuwe, nog ongeziene video wordt `youtube_tracker_nieuwe_video` afgevuurd
met: `kanaal`, `channel_id`, `video_id`, `titel`, `url`, `thumbnail` en `gepubliceerd`.

### Beperkingen

- **Het archief werkt alleen vooruit.** Zodra je een kanaal toevoegt krijg je de
  vijftien video's die op dat moment in de feed staan; wat daarvóór is gepost, is niet
  meer op te halen. Vanaf dat moment mis je niets meer
- Staat Home Assistant lang uit en post het kanaal ondertussen meer dan vijftien
  video's, dan mis je het verschil alsnog
- Home Assistant kan **niet** zien dat je een video op youtube.com bekijkt; markeren
  gebeurt via `markeer_url`, `kijk_url` of een service
- De `UULF`-prefix is een niet-gedocumenteerde YouTube-truc; afgelopen livestreams
  kunnen er soms nog in zitten
- Bij het toevoegen van een kanaal wordt de eerste ronde stil verwerkt, anders krijg je
  vijftien meldingen ineens. Daarna levert elke nieuwe video een event op, ook video's
  die verschenen terwijl Home Assistant uit stond
- Het attribuut toont maximaal 50 video's; de teller zelf telt er wel meer
- Markeringen en het archief worden na 400 dagen opgeruimd

### Hoe het in elkaar zit

Wil je weten hoe de integratie is opgebouwd, of wil je eraan meesleutelen? De
opzet per laag en per bestand staat in [`ARCHITECTURE.md`](ARCHITECTURE.md).

### Ideeën en geschiedenis

Toekomstige uitbreidingen en ideeën staan in [`ROADMAP.md`](ROADMAP.md). De
wijzigingsgeschiedenis per versie staat in de
[release notes](https://github.com/Sarnog/ha-youtube-tracker/releases).

### Merken

YouTube en het YouTube-logo zijn handelsmerken van Google LLC. Deze integratie is
een hobbyproject en heeft geen enkele band met Google of YouTube; ze wordt er niet
door gemaakt, gesteund of goedgekeurd.

### Steun dit project ☕

Vind je deze integratie nuttig? Een kleine bijdrage houdt de koffie warm
en de commits komend. Volledig vrijblijvend natuurlijk!

<!-- Ko-fi badge via shields.io, geen externe tracking -->
[![Koop me een koffie op Ko-fi](https://img.shields.io/badge/Ko--fi-Koop%20me%20een%20koffie-FF5E5B?style=for-the-badge&logo=kofi&logoColor=white)](https://ko-fi.com/sarnog)

<!-- GitHub Sponsors badge, toont live het aantal sponsors -->
[![Sponsor via GitHub](https://img.shields.io/github/sponsors/sarnog?style=for-the-badge&logo=github&label=Sponsors&color=EA4AAA)](https://github.com/sponsors/sarnog)


---



##### <ins>EN</ins>

Tracks how many videos you have not watched yet, per YouTube channel, with a list of
those videos as an attribute so you can put them straight on your dashboard.

<table>
  <tr>
    <td>Add integration:</td>
    <td><a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=Sarnog&amp;repository=ha-youtube-tracker&amp;category=integration"><img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="Open your Home Assistant instance and open a repository inside the Home Assistant Community Store."></a></td>
  </tr>
</table>

**Install through HACS as a custom repository, or manually - see [Installation](#installation).**

### What this does

You add one integration entry per channel. Every channel gets a sensor whose value is
the number of unwatched videos, with the videos themselves as an attribute.

- The data source is YouTube's public RSS feed: no API key, no quota
- Uses the `UULF` playlist, so **without Shorts**
- The `videos` attribute holds the title, URL, thumbnail, publication date and two click links
- Watched videos are stored persistently and survive a restart
- One click marks a video as watched, with or without opening it

**More than fifteen videos.** YouTube's feed only shows about fifteen videos per
channel. That is a window, not an archive: video number sixteen drops out of it. This
integration therefore writes down what it sees on every round and keeps that itself.
YouTube's window moves on, your list does not - a video only disappears once you clear
it yourself.

Requires Home Assistant **2025.6.0** or newer.

### Installation

**Through HACS** (recommended): click the HACS badge at the top of this file, or add
this repository manually as a **custom repository** in HACS (HACS > three dots >
Custom repositories > this GitHub URL, category "Integration").

**Manually**, as an alternative:

1. Copy the `custom_components/youtube_tracker` folder into the `custom_components`
   folder of your Home Assistant configuration.
2. Restart Home Assistant.

Then add channels through **Settings > Devices & services > Add integration >
YouTube Tracker**. You can enter a channel ID (`UC...`), an `@handle` or a full
channel URL.

### Per-channel settings

| Option | Default | Explanation |
| --- | --- | --- |
| Count videos starting from | Start of last month | Cut-off date, rolling per month |
| Number of days back | 30 | Only in "number of days" mode, 365 at most |
| Refresh every | 30 minutes | 10 minutes at minimum |

The cut-off date is calculated in your Home Assistant's time zone, so "the start of
last month" really is midnight where you are, not in UTC.

### Services

| Service | Explanation |
| --- | --- |
| `youtube_tracker.mark_watched` | Mark a single video (`video_id` or `url`) |
| `youtube_tracker.mark_unwatched` | Put a single video back to unwatched |
| `youtube_tracker.mark_all_watched` | Clear everything, optionally per sensor through `entity_id` |

### On your dashboard

Every video in the `videos` attribute carries two links:

| Link | What it does |
| --- | --- |
| `kijk_url` | Marks the video as watched **and** opens it on YouTube |
| `markeer_url` | Only clears the video; you stay on your dashboard |

The second one is handy when you already watched a video outside Home Assistant. It
replies with an empty HTTP 204, which keeps your browser from navigating away. The
sensor changes, so the card updates itself.

An example using a markdown card:

```yaml
type: markdown
content: |
  {% for video in state_attr('sensor.youtube_channelname', 'videos') %}
  [![]({{ video.thumbnail }})]({{ video.kijk_url }})

  **[{{ video.titel }}]({{ video.kijk_url }})** - [clear]({{ video.markeer_url }})
  {% endfor %}
```

Both links work without a login, because otherwise they would not work from a
notification. Instead of a password, the URL carries a per-video signature that only
your Home Assistant can produce. An intercepted link therefore only covers that one
video, never your whole list.

### Event

When a new, still unwatched video shows up, `youtube_tracker_nieuwe_video` is fired
with: `kanaal`, `channel_id`, `video_id`, `titel`, `url`, `thumbnail` and `gepubliceerd`.

### Limitations

- **The archive only works going forward.** The moment you add a channel you get the
  fifteen videos that happen to be in the feed; anything posted before that is out of
  reach. From that point on you miss nothing
- If Home Assistant stays down for a long time and the channel posts more than fifteen
  videos meanwhile, you still miss the difference
- Home Assistant **cannot** tell that you are watching a video on youtube.com; marking
  happens through `markeer_url`, `kijk_url` or a service
- The `UULF` prefix is an undocumented YouTube trick; finished livestreams can still
  turn up in it occasionally
- When you add a channel the first round is processed silently, otherwise you would get
  fifteen notifications at once. After that every new video produces an event, including
  videos that appeared while Home Assistant was down
- The attribute shows 50 videos at most; the counter itself does count beyond that
- Markings and the archive are cleaned up after 400 days

### How it fits together

Want to know how the integration is built, or fancy tinkering with it? The setup
per layer and per file lives in [`ARCHITECTURE.md`](ARCHITECTURE.md).

### Ideas and history

Future additions and ideas live in [`ROADMAP.md`](ROADMAP.md). The per-version change
history lives in the
[release notes](https://github.com/Sarnog/ha-youtube-tracker/releases).

### Trademarks

YouTube and the YouTube logo are trademarks of Google LLC. This integration is a
hobby project with no connection to Google or YouTube whatsoever; it is not made,
endorsed or approved by them.

### Support this project ☕

Do you find this integration useful? A small contribution keeps the coffee warm and
the commits coming. Entirely optional, of course!

<!-- Ko-fi badge via shields.io, no external tracking -->
[![Buy me a coffee on Ko-fi](https://img.shields.io/badge/Ko--fi-Buy%20me%20a%20coffee-FF5E5B?style=for-the-badge&logo=kofi&logoColor=white)](https://ko-fi.com/sarnog)

<!-- GitHub Sponsors badge, shows the sponsor count live -->
[![Sponsor via GitHub](https://img.shields.io/github/sponsors/sarnog?style=for-the-badge&logo=github&label=Sponsors&color=EA4AAA)](https://github.com/sponsors/sarnog)
