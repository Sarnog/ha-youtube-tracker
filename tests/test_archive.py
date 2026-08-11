"""Tests voor het eigen video-archief.

De kern: YouTube toont maar ongeveer 15 video's per kanaal. Zodra er een
zestiende bijkomt, valt de oudste uit de feed. Het archief moet die dan nog
steeds kennen, want anders verdwijnt een video die je nog niet hebt afgevinkt.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from homeassistant.core import HomeAssistant

from custom_components.youtube_tracker.archive import VideoArchive
from custom_components.youtube_tracker.const import MAX_ARCHIVE_PER_CHANNEL

KANAAL = "UCaBcDeFgHiJkLmNoPqRsTuV"
VENSTER = 15  # zoveel video's geeft YouTube maximaal terug
START = datetime(2026, 7, 1, tzinfo=UTC)


def maak_video(nummer: int) -> dict:
    """Maak video nummer N, met een oplopende publicatiedatum."""
    return {
        "video_id": f"video{nummer:06d}",
        "titel": f"Aflevering {nummer}",
        "url": f"https://www.youtube.com/watch?v=video{nummer:06d}",
        "thumbnail": "https://i.ytimg.com/vi/x/hqdefault.jpg",
        "gepubliceerd": START + timedelta(hours=nummer),
    }


def feed_venster(tot_en_met: int) -> list[dict]:
    """Boots de feed na: de laatste 15 video's, nieuwste eerst."""
    vanaf = max(1, tot_en_met - VENSTER + 1)
    return [maak_video(n) for n in range(tot_en_met, vanaf - 1, -1)]


async def maak_archief(hass: HomeAssistant) -> VideoArchive:
    """Geef een geladen, leeg archief terug."""
    archief = VideoArchive(hass)
    await archief.async_load()
    return archief


# --- Het punt van de hele exercitie -----------------------------------------


async def test_videos_blijven_bewaard_als_ze_uit_de_feed_vallen(hass: HomeAssistant):
    """Na 25 uploads kent het archief er 25, terwijl de feed er 15 gaf."""
    archief = await maak_archief(hass)

    await archief.async_add(KANAAL, feed_venster(15))
    await archief.async_add(KANAAL, feed_venster(20))
    await archief.async_add(KANAAL, feed_venster(25))

    bewaard = archief.videos(KANAAL)
    assert len(bewaard) == 25
    # Video 1 is allang uit het venster van YouTube verdwenen
    assert any(video["video_id"] == "video000001" for video in bewaard)


async def test_archief_overleeft_een_herstart(hass: HomeAssistant):
    """Een nieuwe instantie leest gewoon terug wat er op schijf staat."""
    archief = await maak_archief(hass)
    await archief.async_add(KANAAL, feed_venster(15))
    await archief.async_add(KANAAL, feed_venster(20))

    na_herstart = await maak_archief(hass)

    assert len(na_herstart.videos(KANAAL)) == 20
    assert na_herstart.kent_kanaal(KANAAL)


# --- Wat er als "nieuw" wordt gemeld ----------------------------------------


async def test_eerste_ronde_levert_een_onbekend_kanaal_op(hass: HomeAssistant):
    """Zolang we het kanaal niet kennen, hoort de coordinator stil te vullen."""
    archief = await maak_archief(hass)

    assert not archief.kent_kanaal(KANAAL)
    await archief.async_add(KANAAL, feed_venster(15))
    assert archief.kent_kanaal(KANAAL)


async def test_alleen_echt_nieuwe_videos_worden_gemeld(hass: HomeAssistant):
    """De tweede ronde meldt alleen wat er sinds de eerste bij kwam."""
    archief = await maak_archief(hass)
    await archief.async_add(KANAAL, feed_venster(15))

    nieuw = await archief.async_add(KANAAL, feed_venster(18))

    assert nieuw == {"video000016", "video000017", "video000018"}


async def test_dezelfde_feed_nogmaals_levert_niets_nieuws(hass: HomeAssistant):
    """Een ronde zonder uploads hoort niets te melden."""
    archief = await maak_archief(hass)
    await archief.async_add(KANAAL, feed_venster(15))

    nieuw = await archief.async_add(KANAAL, feed_venster(15))

    assert nieuw == set()


async def test_een_leeg_kanaal_wordt_toch_onthouden(hass: HomeAssistant):
    """Ook zonder video's moeten we weten dat we het kanaal al gezien hebben."""
    archief = await maak_archief(hass)

    nieuw = await archief.async_add(KANAAL, [])

    assert nieuw == set()
    assert archief.kent_kanaal(KANAAL)


# --- Inhoud en volgorde -----------------------------------------------------


async def test_nieuwste_video_staat_bovenaan(hass: HomeAssistant):
    """De lijst gaat naar het dashboard, dus nieuwste eerst."""
    archief = await maak_archief(hass)
    await archief.async_add(KANAAL, feed_venster(20))

    bewaard = archief.videos(KANAAL)

    assert bewaard[0]["video_id"] == "video000020"
    assert bewaard[-1]["video_id"] == "video000006"


async def test_velden_blijven_behouden(hass: HomeAssistant):
    """Titel, URL, thumbnail en datum moeten de rondreis overleven."""
    archief = await maak_archief(hass)
    origineel = maak_video(1)
    await archief.async_add(KANAAL, [origineel])

    bewaard = archief.videos(KANAAL)[0]

    assert bewaard["titel"] == origineel["titel"]
    assert bewaard["url"] == origineel["url"]
    assert bewaard["thumbnail"] == origineel["thumbnail"]
    assert bewaard["gepubliceerd"] == origineel["gepubliceerd"]


async def test_video_zonder_datum_wordt_overgeslagen(hass: HomeAssistant):
    """Zonder datum telt een video nooit mee, en is hij ook nooit op te ruimen."""
    archief = await maak_archief(hass)
    zonder_datum = maak_video(1) | {"gepubliceerd": None}

    nieuw = await archief.async_add(KANAAL, [zonder_datum, maak_video(2)])

    assert nieuw == {"video000002"}
    assert len(archief.videos(KANAAL)) == 1


async def test_kanalen_staan_los_van_elkaar(hass: HomeAssistant):
    """Twee kanalen mogen elkaars archief niet zien."""
    archief = await maak_archief(hass)
    ander_kanaal = "UCzZzZzZzZzZzZzZzZzZzZzZ"

    await archief.async_add(KANAAL, feed_venster(5))
    await archief.async_add(ander_kanaal, [maak_video(99)])

    assert len(archief.videos(KANAAL)) == 5
    assert len(archief.videos(ander_kanaal)) == 1


# --- Opruimen ---------------------------------------------------------------


async def test_te_oude_videos_worden_opgeruimd(hass: HomeAssistant):
    """Video's die nooit meer kunnen meetellen mogen weg."""
    archief = await maak_archief(hass)
    lang_geleden = datetime.now(UTC) - timedelta(days=500)
    recent = datetime.now(UTC) - timedelta(days=5)

    await archief.async_add(
        KANAAL,
        [
            maak_video(1) | {"gepubliceerd": lang_geleden},
            maak_video(2) | {"gepubliceerd": recent},
        ],
    )
    await archief.async_purge()

    overgebleven = archief.videos(KANAAL)
    assert [video["video_id"] for video in overgebleven] == ["video000002"]


async def test_bovengrens_per_kanaal(hass: HomeAssistant):
    """Bij heel veel uploads houden we alleen de nieuwste over."""
    archief = await maak_archief(hass)
    teveel = [maak_video(n) for n in range(1, MAX_ARCHIVE_PER_CHANNEL + 51)]

    await archief.async_add(KANAAL, teveel)

    bewaard = archief.videos(KANAAL)
    assert len(bewaard) == MAX_ARCHIVE_PER_CHANNEL
    # De nieuwste hoort erbij te zitten, de oudste niet meer
    assert bewaard[0]["video_id"] == f"video{MAX_ARCHIVE_PER_CHANNEL + 50:06d}"
    assert all(video["video_id"] != "video000001" for video in bewaard)


async def test_bovengrens_kijkt_naar_het_moment_niet_naar_de_tekst(
    hass: HomeAssistant,
):
    """Sorteren op de opgeslagen tekst zou hier de verkeerde weggooien.

    "11:30+02:00" komt als tekst na "10:00+00:00", terwijl dat moment juist
    een half uur eerder ligt.
    """
    archief = await maak_archief(hass)
    andere_zone = ZoneInfo("Europe/Amsterdam")

    # De twee twijfelgevallen zijn de oudste; ze liggen een half uur uit elkaar
    vroeger = maak_video(9001) | {
        "gepubliceerd": datetime(2026, 9, 1, 11, 30, tzinfo=andere_zone)  # 09:30 UTC
    }
    later = maak_video(9002) | {"gepubliceerd": datetime(2026, 9, 1, 10, 0, tzinfo=UTC)}

    # Vul aan tot een boven de grens, met video's die allemaal nieuwer zijn.
    # Er valt dus precies een video af: de oudste van de twee hierboven.
    later_start = datetime(2026, 9, 2, tzinfo=UTC)
    vulling = [
        maak_video(n) | {"gepubliceerd": later_start + timedelta(hours=n)}
        for n in range(1, MAX_ARCHIVE_PER_CHANNEL)
    ]

    await archief.async_add(KANAAL, [*vulling, vroeger, later])

    bewaard = {video["video_id"] for video in archief.videos(KANAAL)}
    assert len(bewaard) == MAX_ARCHIVE_PER_CHANNEL
    # Op tekst gesorteerd zou "11:30+02:00" juist de nieuwste lijken, en zou
    # de verkeerde van de twee sneuvelen
    assert "video009002" in bewaard
    assert "video009001" not in bewaard


async def test_kanaal_verwijderen(hass: HomeAssistant):
    """Verwijder je een kanaal, dan gaat zijn archief mee."""
    archief = await maak_archief(hass)
    await archief.async_add(KANAAL, feed_venster(10))

    await archief.async_remove_channel(KANAAL)

    assert not archief.kent_kanaal(KANAAL)
    assert archief.videos(KANAAL) == []


async def test_onbekend_kanaal_geeft_een_lege_lijst(hass: HomeAssistant):
    """Vragen naar een kanaal dat we niet kennen mag niet stukgaan."""
    archief = await maak_archief(hass)

    assert archief.videos("UCbestaatNietbestaatNiet") == []
