"""Tests voor het event dat bij een nieuwe video wordt afgevuurd.

De meegeleverde blueprint bouwt hier volledig op: de melding haalt de titel,
de klik-links en het aantal ongeziene video's rechtstreeks uit het event en
zoekt de sensor niet op. Ontbreekt hier een veld, dan valt de melding stil.
"""

from __future__ import annotations

import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
)

from homeassistant.core import HomeAssistant

from custom_components.youtube_tracker.archive import VideoArchive
from custom_components.youtube_tracker.const import (
    CONF_CHANNEL_ID,
    CONF_CHANNEL_NAME,
    DOMAIN,
    EVENT_NIEUWE_VIDEO,
    FEED_URL,
    FEED_URL_FALLBACK,
)
from custom_components.youtube_tracker.coordinator import YouTubeChannelCoordinator
from custom_components.youtube_tracker.store import WatchedStore

KANAAL_ID = "UCaBcDeFgHiJkLmNoPqRsTuV"
UULF_URL = FEED_URL.format("UULFaBcDeFgHiJkLmNoPqRsTuV")
TERUGVAL_URL = FEED_URL_FALLBACK.format(KANAAL_ID)

# De fixture-video's staan in juli en augustus 2026; met deze bevroren klok
# valt "begin van de vorige maand" op 1 juli en tellen ze alle drie mee
NU = "2026-08-12 09:00:00+00:00"


@pytest.fixture
async def coordinator(hass: HomeAssistant, aioclient_mock) -> YouTubeChannelCoordinator:
    """Geef een coordinator met eigen, lege opslag.

    aioclient_mock staat hier bewust als afhankelijkheid: de coordinator pakt
    in zijn __init__ de HTTP-sessie op, en die moet op dat moment al vervangen
    zijn. Anders gaat de test echt het internet op.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_CHANNEL_ID: KANAAL_ID, CONF_CHANNEL_NAME: "Testkanaal"},
        unique_id=KANAAL_ID,
    )
    entry.add_to_hass(hass)

    store = WatchedStore(hass)
    await store.async_load()
    archive = VideoArchive(hass)
    await archive.async_load()

    return YouTubeChannelCoordinator(hass, entry, store, archive)


async def _kanaal_al_bekend(coordinator: YouTubeChannelCoordinator) -> None:
    """Doe alsof het kanaal al eerder is opgehaald.

    Anders zou de eerstvolgende ronde de stille eerste ronde zijn en zou er
    niets gemeld worden. Dit gaat rechtstreeks langs het archief, zodat er
    geen tweede feed nodig is.
    """
    await coordinator.archive.async_add(KANAAL_ID, [])


async def test_eerste_ronde_meldt_niets(
    hass: HomeAssistant, coordinator, aioclient_mock, lees_fixture, freezer
):
    """Een net toegevoegd kanaal hoort geen stortvloed aan meldingen te geven."""
    freezer.move_to(NU)
    events = async_capture_events(hass, EVENT_NIEUWE_VIDEO)

    aioclient_mock.get(UULF_URL, text=lees_fixture("feed_uulf.xml"))
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert events == []


async def test_nieuwe_videos_geven_een_event(
    hass: HomeAssistant, coordinator, aioclient_mock, lees_fixture, freezer
):
    """Zodra het kanaal bekend is, levert elke nieuwe video een melding op."""
    freezer.move_to(NU)
    await _kanaal_al_bekend(coordinator)

    events = async_capture_events(hass, EVENT_NIEUWE_VIDEO)
    aioclient_mock.get(UULF_URL, text=lees_fixture("feed_uulf.xml"))
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert len(events) == 3


async def test_event_bevat_alles_wat_een_melding_nodig_heeft(
    hass: HomeAssistant, coordinator, aioclient_mock, lees_fixture, freezer
):
    """De blueprint leest deze velden; ze horen er allemaal in te zitten."""
    freezer.move_to(NU)
    await _kanaal_al_bekend(coordinator)

    events = async_capture_events(hass, EVENT_NIEUWE_VIDEO)
    aioclient_mock.get(UULF_URL, text=lees_fixture("feed_uulf.xml"))
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    nieuwste = next(e for e in events if e.data["video_id"] == "ccccccccccc")

    assert nieuwste.data["kanaal"] == "Testkanaal"
    assert nieuwste.data["channel_id"] == KANAAL_ID
    assert nieuwste.data["titel"] == "De nieuwste video"
    assert nieuwste.data["url"] == "https://www.youtube.com/watch?v=ccccccccccc"
    assert nieuwste.data["thumbnail"].startswith("https://")
    assert nieuwste.data["gepubliceerd"].startswith("2026-08-05")


async def test_event_bevat_werkende_klik_links(
    hass: HomeAssistant, coordinator, aioclient_mock, lees_fixture, freezer
):
    """De links moeten precies zo geldig zijn als die in het sensor-attribuut."""
    freezer.move_to(NU)
    await _kanaal_al_bekend(coordinator)

    events = async_capture_events(hass, EVENT_NIEUWE_VIDEO)
    aioclient_mock.get(UULF_URL, text=lees_fixture("feed_uulf.xml"))
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    nieuwste = next(e for e in events if e.data["video_id"] == "ccccccccccc")
    handtekening = coordinator.store.maak_handtekening("ccccccccccc")

    assert nieuwste.data["kijk_url"] == (
        f"/api/youtube_tracker/ccccccccccc/{handtekening}"
    )
    assert nieuwste.data["markeer_url"] == (
        f"/api/youtube_tracker/ccccccccccc/{handtekening}?open=0"
    )
    assert coordinator.store.controleer_handtekening("ccccccccccc", handtekening)


async def test_event_telt_de_ongeziene_videos(
    hass: HomeAssistant, coordinator, aioclient_mock, lees_fixture, freezer
):
    """Het aantal in de melding moet het totaal van het kanaal zijn."""
    freezer.move_to(NU)
    await _kanaal_al_bekend(coordinator)

    events = async_capture_events(hass, EVENT_NIEUWE_VIDEO)
    aioclient_mock.get(UULF_URL, text=lees_fixture("feed_uulf.xml"))
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Alle drie de fixture-video's tellen mee, dus elk event meldt er drie
    assert {e.data["ongezien"] for e in events} == {3}


async def test_afgevinkte_video_telt_niet_mee(
    hass: HomeAssistant, coordinator, aioclient_mock, lees_fixture, freezer
):
    """Wat je al hebt afgevinkt hoort niet mee te tellen en niet te melden."""
    freezer.move_to(NU)
    await _kanaal_al_bekend(coordinator)
    await coordinator.store.async_mark("ccccccccccc")

    events = async_capture_events(hass, EVENT_NIEUWE_VIDEO)
    aioclient_mock.get(UULF_URL, text=lees_fixture("feed_uulf.xml"))
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    gemeld = {e.data["video_id"] for e in events}
    assert "ccccccccccc" not in gemeld
    assert {e.data["ongezien"] for e in events} == {2}
