"""Tests voor de bekeken-lijst en de handtekeningen in de kijk-links."""

from __future__ import annotations

import re
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.youtube_tracker.const import (
    SIGNAL_WATCHED_UPDATED,
    SIGNATURE_LENGTH,
)
from custom_components.youtube_tracker.store import WatchedStore

VIDEO_A = "aaaaaaaaaaa"
VIDEO_B = "bbbbbbbbbbb"


async def maak_store(hass: HomeAssistant) -> WatchedStore:
    """Geef een geladen, lege opslag terug."""
    store = WatchedStore(hass)
    await store.async_load()
    return store


# --- Markeren en terugdraaien -----------------------------------------------


async def test_markeren_en_uitlezen(hass: HomeAssistant):
    """Een gemarkeerde video geldt als bekeken, een andere niet."""
    store = await maak_store(hass)

    await store.async_mark(VIDEO_A)

    assert store.is_watched(VIDEO_A)
    assert not store.is_watched(VIDEO_B)


async def test_meerdere_tegelijk_markeren(hass: HomeAssistant):
    """De service mark_all_watched geeft een hele lijst door."""
    store = await maak_store(hass)

    aantal = await store.async_mark([VIDEO_A, VIDEO_B])

    assert aantal == 2


async def test_dubbel_markeren_telt_maar_een_keer(hass: HomeAssistant):
    """Twee keer hetzelfde afvinken is geen wijziging meer."""
    store = await maak_store(hass)
    await store.async_mark(VIDEO_A)

    aantal = await store.async_mark(VIDEO_A)

    assert aantal == 0


async def test_terugzetten_op_ongezien(hass: HomeAssistant):
    """mark_unwatched moet de markering echt weghalen."""
    store = await maak_store(hass)
    await store.async_mark(VIDEO_A)

    aantal = await store.async_unmark(VIDEO_A)

    assert aantal == 1
    assert not store.is_watched(VIDEO_A)


async def test_onbekende_video_terugzetten_doet_niets(hass: HomeAssistant):
    """Iets terugzetten dat nooit gemarkeerd was is geen wijziging."""
    store = await maak_store(hass)

    assert await store.async_unmark(VIDEO_A) == 0


async def test_markeringen_overleven_een_herstart(hass: HomeAssistant):
    """Na een herstart moet je afgevinkte lijst er nog zijn."""
    store = await maak_store(hass)
    await store.async_mark(VIDEO_A)

    na_herstart = await maak_store(hass)

    assert na_herstart.is_watched(VIDEO_A)


async def test_sensors_krijgen_een_seintje(hass: HomeAssistant):
    """Na het afvinken moeten de sensors hun waarde opnieuw berekenen."""
    store = await maak_store(hass)
    seintjes = []

    from homeassistant.helpers.dispatcher import async_dispatcher_connect

    async_dispatcher_connect(hass, SIGNAL_WATCHED_UPDATED, lambda: seintjes.append(1))

    await store.async_mark(VIDEO_A)
    await hass.async_block_till_done()

    assert len(seintjes) == 1


# --- Opruimen ---------------------------------------------------------------


async def test_oude_markeringen_worden_opgeruimd(hass: HomeAssistant):
    """Markeringen ouder dan de bewaartermijn mogen weg."""
    store = await maak_store(hass)
    await store.async_mark(VIDEO_A)
    # Zet de markering handmatig ver in het verleden
    store._watched[VIDEO_A] = (dt_util.utcnow() - timedelta(days=500)).isoformat()

    await store.async_purge()

    assert not store.is_watched(VIDEO_A)


async def test_onleesbare_tijdstippen_worden_opgeruimd(hass: HomeAssistant):
    """Rommel in de opslag mag de opschoning niet laten struikelen."""
    store = await maak_store(hass)
    store._watched["kapot"] = "dit is geen datum"

    await store.async_purge()

    assert not store.is_watched("kapot")


# --- Handtekeningen ---------------------------------------------------------


async def test_handtekening_is_url_veilig(hass: HomeAssistant):
    """De handtekening staat in een pad, dus mag hij niets bijzonders bevatten."""
    store = await maak_store(hass)

    handtekening = store.maak_handtekening(VIDEO_A)

    assert len(handtekening) == SIGNATURE_LENGTH
    assert re.fullmatch(r"[A-Za-z0-9_-]+", handtekening)


async def test_handtekening_is_per_video_verschillend(hass: HomeAssistant):
    """Dit is de hele reden voor een handtekening in plaats van een vast token."""
    store = await maak_store(hass)

    assert store.maak_handtekening(VIDEO_A) != store.maak_handtekening(VIDEO_B)


async def test_eigen_handtekening_wordt_geaccepteerd(hass: HomeAssistant):
    """De link die we zelf in het attribuut zetten moet natuurlijk werken."""
    store = await maak_store(hass)

    assert store.controleer_handtekening(VIDEO_A, store.maak_handtekening(VIDEO_A))


async def test_handtekening_van_een_andere_video_wordt_geweigerd(hass: HomeAssistant):
    """Wie de link van video A onderschept, kan daarmee niets bij video B."""
    store = await maak_store(hass)

    assert not store.controleer_handtekening(VIDEO_B, store.maak_handtekening(VIDEO_A))


async def test_verzonnen_handtekening_wordt_geweigerd(hass: HomeAssistant):
    """Zomaar iets intypen mag niet werken."""
    store = await maak_store(hass)

    assert not store.controleer_handtekening(VIDEO_A, "zomaarwatletters123")
    assert not store.controleer_handtekening(VIDEO_A, "")


async def test_geheim_blijft_gelijk_na_een_herstart(hass: HomeAssistant):
    """Anders zouden alle links op je dashboard bij elke herstart breken."""
    store = await maak_store(hass)
    handtekening = store.maak_handtekening(VIDEO_A)

    na_herstart = await maak_store(hass)

    assert na_herstart.controleer_handtekening(VIDEO_A, handtekening)
