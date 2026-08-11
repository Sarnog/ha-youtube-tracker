"""Sensorplatform van de YouTube Tracker integratie."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    MARK_URL,
    MAX_VIDEOS_IN_ATTRIBUTE,
    SIGNAL_WATCHED_UPDATED,
    VIEW_URL,
)
from .coordinator import YouTubeChannelCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Zet de sensor op voor dit kanaal."""
    coordinator: YouTubeChannelCoordinator = hass.data[DOMAIN]["entries"][
        entry.entry_id
    ]
    async_add_entities([YouTubeTrackerSensor(coordinator)])


class YouTubeTrackerSensor(CoordinatorEntity[YouTubeChannelCoordinator], SensorEntity):
    """Toont hoeveel video's van dit kanaal nog niet bekeken zijn."""

    _attr_icon = "mdi:youtube"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "video's"
    _attr_has_entity_name = False
    # De videolijst is groot en verandert vaak. Zonder dit zou hij bij elke
    # wijziging opnieuw in de recorder-database belanden en die flink laten
    # groeien. De teller zelf blijft gewoon in de historie staan.
    _unrecorded_attributes = frozenset({"videos"})

    def __init__(self, coordinator: YouTubeChannelCoordinator) -> None:
        """Initialiseer de sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.channel_id}_ongezien"
        self._attr_name = f"YouTube {coordinator.channel_name}"

    async def async_added_to_hass(self) -> None:
        """Luister naar wijzigingen in de bekeken-lijst."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_WATCHED_UPDATED, self._async_opnieuw_berekenen
            )
        )

    @callback
    def _async_opnieuw_berekenen(self) -> None:
        """Werk de sensor bij nadat er iets is afgevinkt."""
        self.async_write_ha_state()

    @property
    def native_value(self) -> int:
        """Geef het aantal ongeziene video's."""
        return len(self.coordinator.ongeziene_videos())

    @property
    def entity_picture(self) -> str | None:
        """Toon de thumbnail van de nieuwste ongeziene video."""
        if ongezien := self.coordinator.ongeziene_videos():
            return ongezien[0]["thumbnail"]
        return None

    @property
    def extra_state_attributes(self) -> dict:
        """Geef de lijst met ongeziene video's en wat kanaalinformatie."""
        ongezien = self.coordinator.ongeziene_videos()
        store = self.coordinator.store

        videos = [
            self._als_attribuut(video, store.maak_handtekening(video["video_id"]))
            for video in ongezien[:MAX_VIDEOS_IN_ATTRIBUTE]
        ]

        return {
            "kanaal": self.coordinator.channel_name,
            "channel_id": self.coordinator.channel_id,
            "peildatum": self.coordinator.peildatum.isoformat(),
            "videos": videos,
            "nieuwste_titel": videos[0]["titel"] if videos else None,
            "nieuwste_url": videos[0]["url"] if videos else None,
        }

    @staticmethod
    def _als_attribuut(video: dict, handtekening: str) -> dict:
        """Zet een video om naar de vorm die op je dashboard terechtkomt.

        De twee links markeren de video allebei als bekeken. De eerste opent
        hem daarna op YouTube, de tweede laat je staan waar je bent. De
        handtekening geldt alleen voor deze ene video.
        """
        return {
            "video_id": video["video_id"],
            "titel": video["titel"],
            "url": video["url"],
            "kijk_url": VIEW_URL.format(
                video_id=video["video_id"], signature=handtekening
            ),
            "markeer_url": MARK_URL.format(
                video_id=video["video_id"], signature=handtekening
            ),
            "thumbnail": video["thumbnail"],
            "gepubliceerd": video["gepubliceerd"].isoformat()
            if video["gepubliceerd"]
            else None,
        }
