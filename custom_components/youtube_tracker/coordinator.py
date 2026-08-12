"""Coordinator die per kanaal de feed bijhoudt."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .archive import VideoArchive
from .const import (
    CONF_CHANNEL_ID,
    CONF_CHANNEL_NAME,
    CONF_LOOKBACK_DAYS,
    CONF_LOOKBACK_MODE,
    CONF_SCAN_INTERVAL,
    DEFAULT_LOOKBACK_DAYS,
    DEFAULT_LOOKBACK_MODE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EVENT_NIEUWE_VIDEO,
    MARK_URL,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    MODE_VORIGE_MAAND,
    VIEW_URL,
)
from .feed import FeedError, async_fetch_feed
from .store import WatchedStore

_LOGGER = logging.getLogger(__name__)


def bereken_peildatum(modus: str, dagen: int) -> datetime:
    """Bepaal vanaf welk moment video's meetellen. Geeft UTC terug.

    "Begin van de vorige maand" wordt in de tijdzone van Home Assistant
    berekend, niet in UTC. Anders begint de maand voor ons om 02:00 in plaats
    van om middernacht, en vallen video's uit dat gaatje er net buiten.
    """
    if modus == MODE_VORIGE_MAAND:
        # Eerste dag van deze maand, dan een dag terug en weer naar dag 1
        vandaag = dt_util.now().date()
        laatste_vorige_maand = vandaag.replace(day=1) - timedelta(days=1)
        eerste_vorige_maand = laatste_vorige_maand.replace(day=1)
        # start_of_local_day zet er middernacht in de juiste tijdzone omheen,
        # inclusief zomer-/wintertijd
        return dt_util.as_utc(dt_util.start_of_local_day(eerste_vorige_maand))

    return dt_util.utcnow() - timedelta(days=dagen)


class YouTubeChannelCoordinator(DataUpdateCoordinator[list[dict]]):
    """Haalt periodiek de feed van één YouTube-kanaal op."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        store: WatchedStore,
        archive: VideoArchive,
    ) -> None:
        """Initialiseer de coordinator."""
        self.store = store
        self.archive = archive
        self.channel_id: str = entry.data[CONF_CHANNEL_ID]
        self.channel_name: str = entry.data.get(CONF_CHANNEL_NAME, self.channel_id)
        self._session = async_get_clientsession(hass)

        # Begrens het interval: de optiepagina doet dat al, maar een via de
        # API aangepaste entry kan er alsnog onzin in zetten
        interval = int(entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        interval = max(MIN_SCAN_INTERVAL, min(MAX_SCAN_INTERVAL, interval))

        super().__init__(
            hass,
            _LOGGER,
            # Expliciet meegeven; Home Assistant leidt dit niet meer zelf af
            # en de entry is via self.config_entry beschikbaar
            config_entry=entry,
            name=f"{DOMAIN} {self.channel_name}",
            update_interval=timedelta(minutes=interval),
        )

    @property
    def peildatum(self) -> datetime:
        """Geef het moment vanaf wanneer video's meetellen."""
        return bereken_peildatum(
            self.config_entry.options.get(CONF_LOOKBACK_MODE, DEFAULT_LOOKBACK_MODE),
            self.config_entry.options.get(CONF_LOOKBACK_DAYS, DEFAULT_LOOKBACK_DAYS),
        )

    async def _async_update_data(self) -> list[dict]:
        """Haal de feed op, vul het archief aan en meld nieuwe video's.

        De feed is maar een venster van ongeveer 15 video's. We geven daarom
        niet de feed terug, maar alles wat we ooit van dit kanaal gezien hebben.
        """
        try:
            kanaalnaam, videos = await async_fetch_feed(self._session, self.channel_id)
        except FeedError as fout:
            raise UpdateFailed(str(fout)) from fout

        if kanaalnaam:
            self.channel_name = kanaalnaam

        # Kennen we dit kanaal nog niet, dan is dit de eerste ronde en vullen
        # we stil: anders krijg je vijftien meldingen zodra je een kanaal
        # toevoegt. Dit staat op schijf, dus een herstart telt niet als eerste
        # ronde en je mist geen meldingen meer over downtime.
        eerste_ronde = not self.archive.kent_kanaal(self.channel_id)
        nieuwe_ids = await self.archive.async_add(self.channel_id, videos)

        alles = self.archive.videos(self.channel_id)

        if not eerste_ronde and nieuwe_ids:
            self._meld_nieuwe_videos(alles, nieuwe_ids)

        return alles

    def _meld_nieuwe_videos(self, videos: list[dict], nieuwe_ids: set[str]) -> None:
        """Vuur een event af voor elke nieuwe video die nog meetelt.

        Het event bevat alles wat een automatisering nodig heeft, zodat die de
        sensor niet hoeft op te zoeken: de klik-links van deze video en hoeveel
        video's van dit kanaal er in totaal nog ongezien zijn.
        """
        peildatum = self.peildatum

        # Te oud om mee te tellen, of al afgevinkt via een service, valt af
        ongezien = [
            video
            for video in videos
            if video["gepubliceerd"]
            and video["gepubliceerd"] >= peildatum
            and not self.store.is_watched(video["video_id"])
        ]

        for video in ongezien:
            if video["video_id"] not in nieuwe_ids:
                continue
            handtekening = self.store.maak_handtekening(video["video_id"])
            self.hass.bus.async_fire(
                EVENT_NIEUWE_VIDEO,
                {
                    "kanaal": self.channel_name,
                    "channel_id": self.channel_id,
                    "video_id": video["video_id"],
                    "titel": video["titel"],
                    "url": video["url"],
                    "thumbnail": video["thumbnail"],
                    "gepubliceerd": video["gepubliceerd"].isoformat(),
                    # Zo kan een melding meteen doorlinken en afvinken
                    "kijk_url": VIEW_URL.format(
                        video_id=video["video_id"], signature=handtekening
                    ),
                    "markeer_url": MARK_URL.format(
                        video_id=video["video_id"], signature=handtekening
                    ),
                    # Inclusief deze video; handig voor "je hebt er nog 5 open"
                    "ongezien": len(ongezien),
                },
            )

    def ongeziene_videos(self) -> list[dict]:
        """Geef de video's die binnen de peildatum vallen en nog ongezien zijn."""
        if not self.data:
            return []

        peildatum = self.peildatum
        return [
            video
            for video in self.data
            if video["gepubliceerd"]
            and video["gepubliceerd"] >= peildatum
            and not self.store.is_watched(video["video_id"])
        ]
