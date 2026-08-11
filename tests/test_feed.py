"""Tests voor het ophalen en parsen van de YouTube-feed."""

from __future__ import annotations

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.youtube_tracker.const import (
    FEED_URL,
    FEED_URL_FALLBACK,
)
from custom_components.youtube_tracker.feed import (
    FeedError,
    _parse_feed,
    async_fetch_feed,
    async_resolve_channel_id,
)

KANAAL_ID = "UCaBcDeFgHiJkLmNoPqRsTuV"
UULF_URL = FEED_URL.format("UULFaBcDeFgHiJkLmNoPqRsTuV")
TERUGVAL_URL = FEED_URL_FALLBACK.format(KANAAL_ID)


# --- Het parsen zelf, zonder netwerk ----------------------------------------


def test_parse_leest_kanaalnaam_en_videos(lees_fixture):
    """Een normale feed levert de kanaalnaam en alle bruikbare video's op."""
    naam, videos = _parse_feed(lees_fixture("feed_uulf.xml"))

    assert naam == "Testkanaal"
    # De vierde entry heeft geen videoId en hoort overgeslagen te worden
    assert len(videos) == 3


def test_parse_sorteert_nieuwste_eerst(lees_fixture):
    """De feed staat door elkaar; wij zetten de nieuwste bovenaan."""
    _, videos = _parse_feed(lees_fixture("feed_uulf.xml"))

    assert [video["video_id"] for video in videos] == [
        "ccccccccccc",  # 5 augustus
        "bbbbbbbbbbb",  # 20 juli
        "aaaaaaaaaaa",  # 1 juli
    ]


def test_parse_haalt_spaties_uit_de_titel(lees_fixture):
    """YouTube laat soms spaties rond de titel staan."""
    _, videos = _parse_feed(lees_fixture("feed_uulf.xml"))

    assert videos[0]["titel"] == "De nieuwste video"


def test_parse_gebruikt_thumbnail_uit_de_feed(lees_fixture):
    """Staat er een media:thumbnail in, dan gebruiken we die."""
    _, videos = _parse_feed(lees_fixture("feed_uulf.xml"))

    assert videos[0]["thumbnail"] == "https://i4.ytimg.com/vi/ccccccccccc/hqdefault.jpg"


def test_parse_valt_terug_op_vaste_thumbnail(lees_fixture):
    """Zonder media:group stellen we de thumbnail-URL zelf samen."""
    _, videos = _parse_feed(lees_fixture("feed_uulf.xml"))

    zonder_thumbnail = next(v for v in videos if v["video_id"] == "bbbbbbbbbbb")
    assert (
        zonder_thumbnail["thumbnail"]
        == "https://i.ytimg.com/vi/bbbbbbbbbbb/hqdefault.jpg"
    )


def test_parse_bouwt_de_video_url(lees_fixture):
    """Elke video krijgt een gewone YouTube-kijk-URL."""
    _, videos = _parse_feed(lees_fixture("feed_uulf.xml"))

    assert videos[0]["url"] == "https://www.youtube.com/watch?v=ccccccccccc"


def test_parse_leest_de_publicatiedatum(lees_fixture):
    """De datum moet een datetime met tijdzone worden, geen tekst."""
    _, videos = _parse_feed(lees_fixture("feed_uulf.xml"))

    gepubliceerd = videos[0]["gepubliceerd"]
    assert gepubliceerd.year == 2026
    assert gepubliceerd.month == 8
    assert gepubliceerd.day == 5
    assert gepubliceerd.tzinfo is not None


def test_parse_van_lege_feed(lees_fixture):
    """Een kanaal zonder video's geeft wel een naam, maar een lege lijst."""
    naam, videos = _parse_feed(lees_fixture("feed_leeg.xml"))

    assert naam == "Leeg Kanaal"
    assert videos == []


def test_parse_van_kapotte_xml():
    """Onleesbare XML wordt een nette FeedError, geen ruwe parserfout."""
    with pytest.raises(FeedError, match="kon niet worden gelezen"):
        _parse_feed("<dit is geen geldige xml")


# --- Het ophalen over het netwerk -------------------------------------------


async def test_fetch_gebruikt_de_uulf_playlist(
    hass: HomeAssistant, aioclient_mock, lees_fixture
):
    """De eerste poging gaat naar de UULF-playlist, dus zonder Shorts."""
    aioclient_mock.get(UULF_URL, text=lees_fixture("feed_uulf.xml"))

    naam, videos = await async_fetch_feed(async_get_clientsession(hass), KANAAL_ID)

    assert naam == "Testkanaal"
    assert len(videos) == 3
    # Er is maar een verzoek nodig geweest: de terugval bleef ongebruikt
    assert len(aioclient_mock.mock_calls) == 1


async def test_fetch_valt_terug_bij_een_fout(
    hass: HomeAssistant, aioclient_mock, lees_fixture
):
    """Geeft de UULF-playlist een foutcode, dan proberen we de kanaalfeed."""
    aioclient_mock.get(UULF_URL, status=404)
    aioclient_mock.get(TERUGVAL_URL, text=lees_fixture("feed_uulf.xml"))

    naam, videos = await async_fetch_feed(async_get_clientsession(hass), KANAAL_ID)

    assert naam == "Testkanaal"
    assert len(videos) == 3
    assert len(aioclient_mock.mock_calls) == 2


async def test_fetch_valt_terug_bij_een_lege_playlist(
    hass: HomeAssistant, aioclient_mock, lees_fixture
):
    """Een lege UULF-playlist is ook een reden om de kanaalfeed te proberen."""
    aioclient_mock.get(UULF_URL, text=lees_fixture("feed_leeg.xml"))
    aioclient_mock.get(TERUGVAL_URL, text=lees_fixture("feed_uulf.xml"))

    _, videos = await async_fetch_feed(async_get_clientsession(hass), KANAAL_ID)

    assert len(videos) == 3


async def test_fetch_van_kanaal_zonder_videos_is_geen_fout(
    hass: HomeAssistant, aioclient_mock, lees_fixture
):
    """Twee lege maar geldige feeds betekent: kanaal bestaat, nog niets erop."""
    aioclient_mock.get(UULF_URL, text=lees_fixture("feed_leeg.xml"))
    aioclient_mock.get(TERUGVAL_URL, text=lees_fixture("feed_leeg.xml"))

    naam, videos = await async_fetch_feed(async_get_clientsession(hass), KANAAL_ID)

    assert naam == "Leeg Kanaal"
    assert videos == []


async def test_fetch_faalt_als_beide_urls_falen(hass: HomeAssistant, aioclient_mock):
    """Is het kanaal onvindbaar, dan hoort er een FeedError te komen."""
    aioclient_mock.get(UULF_URL, status=404)
    aioclient_mock.get(TERUGVAL_URL, status=404)

    with pytest.raises(FeedError, match="status 404"):
        await async_fetch_feed(async_get_clientsession(hass), KANAAL_ID)


# --- Invoer omzetten naar een channel-ID ------------------------------------


async def test_resolve_herkent_een_kaal_channel_id(hass: HomeAssistant):
    """Staat er al een UC-ID in de invoer, dan is geen verzoek nodig."""
    gevonden = await async_resolve_channel_id(
        async_get_clientsession(hass), f"  {KANAAL_ID}  "
    )

    assert gevonden == KANAAL_ID


async def test_resolve_herkent_een_channel_id_in_een_url(hass: HomeAssistant):
    """Een volledige kanaal-URL met UC-ID erin werkt ook zonder verzoek."""
    gevonden = await async_resolve_channel_id(
        async_get_clientsession(hass),
        f"https://www.youtube.com/channel/{KANAAL_ID}/videos",
    )

    assert gevonden == KANAAL_ID


async def test_resolve_zoekt_een_handle_op(hass: HomeAssistant, aioclient_mock):
    """Een @handle wordt opgezocht op de kanaalpagina."""
    aioclient_mock.get(
        "https://www.youtube.com/@testkanaal",
        text=f'<html>...,"channelId":"{KANAAL_ID}",...</html>',
    )

    gevonden = await async_resolve_channel_id(
        async_get_clientsession(hass), "@testkanaal"
    )

    assert gevonden == KANAAL_ID


async def test_resolve_zet_er_zelf_een_apenstaartje_voor(
    hass: HomeAssistant, aioclient_mock
):
    """Wie de @ vergeet, krijgt hem er alsnog voor geplakt."""
    aioclient_mock.get(
        "https://www.youtube.com/@testkanaal",
        text=f'<html>"channelId":"{KANAAL_ID}"</html>',
    )

    gevonden = await async_resolve_channel_id(
        async_get_clientsession(hass), "testkanaal"
    )

    assert gevonden == KANAAL_ID


async def test_resolve_weigert_een_vreemde_host(hass: HomeAssistant):
    """Een URL buiten YouTube wordt geweigerd, zonder verzoek te doen."""
    with pytest.raises(FeedError, match="Alleen YouTube"):
        await async_resolve_channel_id(
            async_get_clientsession(hass), "https://kwaadaardig.example.com/kanaal"
        )


async def test_resolve_faalt_als_de_pagina_geen_id_bevat(
    hass: HomeAssistant, aioclient_mock
):
    """Zonder channelId in de HTML kunnen we niets."""
    aioclient_mock.get(
        "https://www.youtube.com/@bestaatniet", text="<html>Niets te vinden</html>"
    )

    with pytest.raises(FeedError, match="Geen channel-ID"):
        await async_resolve_channel_id(async_get_clientsession(hass), "@bestaatniet")
