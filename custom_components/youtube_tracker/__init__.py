"""De YouTube Tracker integratie."""

from __future__ import annotations

import logging
import re
from datetime import timedelta

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .archive import VideoArchive
from .const import (
    ATTR_ENTITY_ID,
    ATTR_URL,
    ATTR_VIDEO_ID,
    CONF_CHANNEL_ID,
    DOMAIN,
    PURGE_INTERVAL_HOURS,
    SERVICE_MARK_ALL_WATCHED,
    SERVICE_MARK_UNWATCHED,
    SERVICE_MARK_WATCHED,
)
from .coordinator import YouTubeChannelCoordinator
from .store import WatchedStore
from .view import YouTubeWatchView

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

# Deze integratie wordt alleen via de gebruikersinterface ingesteld, dus er
# hoort niets van in configuration.yaml te staan
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# Haalt het video-ID uit een watch-, youtu.be-, shorts- of embed-URL
URL_PATROON = re.compile(r"(?:v=|youtu\.be/|/shorts/|/embed/)([\w-]{11})")

SERVICE_VIDEO_SCHEMA = vol.Schema(
    vol.All(
        {
            vol.Optional(ATTR_VIDEO_ID): cv.string,
            vol.Optional(ATTR_URL): cv.string,
        },
        cv.has_at_least_one_key(ATTR_VIDEO_ID, ATTR_URL),
    )
)

SERVICE_ALL_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTITY_ID): cv.entity_ids})


def _haal_video_id(call: ServiceCall) -> str:
    """Bepaal het video-ID uit de service-aanroep."""
    if video_id := call.data.get(ATTR_VIDEO_ID):
        return video_id

    url = call.data.get(ATTR_URL, "")
    if (treffer := URL_PATROON.search(url)) is not None:
        return treffer.group(1)

    # ServiceValidationError geeft een nette melding in de interface, in
    # plaats van een stacktrace in het logboek
    raise ServiceValidationError(f"Geen geldig video-ID gevonden in: {url}")


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Zet de onderdelen op die alle kanalen delen.

    Dit draait gegarandeerd één keer, vóór het opzetten van de config entries.
    Dat is belangrijk: Home Assistant zet entries van hetzelfde domein parallel
    op, dus als we dit per entry zouden doen, konden twee kanalen tegelijk
    besluiten dat de opslag nog niet bestond.
    """
    store = WatchedStore(hass)
    await store.async_load()

    archive = VideoArchive(hass)
    await archive.async_load()

    hass.data[DOMAIN] = {"store": store, "archive": archive, "entries": {}}

    hass.http.register_view(YouTubeWatchView(store))
    _registreer_services(hass)

    async def _opschonen(_nu) -> None:
        """Ruim periodiek oude markeringen en oude archiefvideo's op."""
        await store.async_purge()
        await archive.async_purge()

    # Zonder dit draait de opschoning alleen bij het opstarten, en dus nooit
    # meer op een Home Assistant die maandenlang doorloopt
    async_track_time_interval(hass, _opschonen, timedelta(hours=PURGE_INTERVAL_HOURS))

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Zet een kanaal op."""
    store: WatchedStore = hass.data[DOMAIN]["store"]
    archive: VideoArchive = hass.data[DOMAIN]["archive"]

    coordinator = YouTubeChannelCoordinator(hass, entry, store, archive)
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN]["entries"][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_gewijzigd))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Verwijder een kanaal."""
    ontladen = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ontladen:
        hass.data[DOMAIN]["entries"].pop(entry.entry_id, None)
    return ontladen


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Gooi het archief weg wanneer een kanaal definitief verwijderd wordt."""
    # Deze functie kan ook draaien als de integratie niet (meer) opgezet is
    if (domein_data := hass.data.get(DOMAIN)) is None:
        return
    archive: VideoArchive = domein_data["archive"]
    await archive.async_remove_channel(entry.data[CONF_CHANNEL_ID])


async def _async_options_gewijzigd(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Herlaad het kanaal wanneer de opties zijn aangepast."""
    await hass.config_entries.async_reload(entry.entry_id)


def _registreer_services(hass: HomeAssistant) -> None:
    """Registreer de services van de integratie."""

    async def markeer_bekeken(call: ServiceCall) -> None:
        """Markeer één video als bekeken."""
        store: WatchedStore = hass.data[DOMAIN]["store"]
        await store.async_mark(_haal_video_id(call))

    async def markeer_ongezien(call: ServiceCall) -> None:
        """Zet één video terug op ongezien."""
        store: WatchedStore = hass.data[DOMAIN]["store"]
        await store.async_unmark(_haal_video_id(call))

    async def markeer_alles_bekeken(call: ServiceCall) -> None:
        """Vink alle ongeziene video's af, eventueel van één kanaal."""
        store: WatchedStore = hass.data[DOMAIN]["store"]
        entity_ids = call.data.get(ATTR_ENTITY_ID)

        video_ids: list[str] = []
        for coordinator in hass.data[DOMAIN]["entries"].values():
            # Zonder entity_id doen we alle kanalen in één keer
            if entity_ids and not _hoort_bij(hass, coordinator, entity_ids):
                continue
            video_ids.extend(
                video["video_id"] for video in coordinator.ongeziene_videos()
            )

        await store.async_mark(video_ids)

    hass.services.async_register(
        DOMAIN, SERVICE_MARK_WATCHED, markeer_bekeken, schema=SERVICE_VIDEO_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_MARK_UNWATCHED, markeer_ongezien, schema=SERVICE_VIDEO_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_MARK_ALL_WATCHED,
        markeer_alles_bekeken,
        schema=SERVICE_ALL_SCHEMA,
    )


def _hoort_bij(
    hass: HomeAssistant,
    coordinator: YouTubeChannelCoordinator,
    entity_ids: list[str],
) -> bool:
    """Controleer of een coordinator bij een van de opgegeven entiteiten hoort."""
    registry = er.async_get(hass)
    for entity_id in entity_ids:
        vermelding = registry.async_get(entity_id)
        if vermelding and vermelding.config_entry_id == coordinator.entry.entry_id:
            return True
    return False
