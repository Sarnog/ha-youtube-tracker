"""Eigen archief van video's die we ooit in de feed hebben zien staan.

YouTube geeft in de RSS-feed maar ongeveer 15 video's per kanaal terug. Dat is
een venster, geen archief: video nummer 16 verdwijnt eruit. Zou de integratie
alleen dat venster gebruiken, dan zou een video die je nog niet had afgevinkt
gewoon uit je lijst verdwijnen.

Daarom schrijven we bij elke ronde op wat we gezien hebben. Het venster van
YouTube schuift op, ons archief niet. Dat werkt alleen vooruit: video's die al
uit de feed waren voordat je het kanaal toevoegde, zijn niet meer op te halen.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    ARCHIVE_RETENTION_DAYS,
    ARCHIVE_STORAGE_KEY,
    MAX_ARCHIVE_PER_CHANNEL,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)


class VideoArchive:
    """Bewaart per kanaal alle video's die ooit in de feed stonden."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialiseer het archief."""
        self.hass = hass
        self._store: Store = Store(hass, STORAGE_VERSION, ARCHIVE_STORAGE_KEY)
        # Structuur: {channel_id: {video_id: {titel, url, thumbnail, gepubliceerd}}}
        # De datum staat op schijf als ISO-tekst, in het geheugen als datetime.
        self._kanalen: dict[str, dict[str, dict]] = {}

    async def async_load(self) -> None:
        """Laad het archief van schijf."""
        data = await self._store.async_load() or {}
        self._kanalen = data.get("channels", {})
        await self.async_purge()

    async def _async_save(self) -> None:
        """Schrijf het archief weg naar schijf."""
        await self._store.async_save({"channels": self._kanalen})

    def kent_kanaal(self, channel_id: str) -> bool:
        """Controleer of we dit kanaal al eerder hebben opgehaald.

        Wordt gebruikt om bij het toevoegen van een kanaal niet meteen vijftien
        meldingen af te vuren: de eerste ronde vullen we stil.
        """
        return channel_id in self._kanalen

    async def async_add(self, channel_id: str, videos: list[dict]) -> set[str]:
        """Voeg video's toe en geef terug welke daarvan nieuw waren.

        Video's zonder publicatiedatum slaan we niet op: die tellen nooit mee
        voor de peildatum, en zonder datum zouden ze ook nooit opgeruimd worden.
        """
        bekend = self._kanalen.setdefault(channel_id, {})
        # Een nieuw kanaal is op zichzelf al een wijziging die bewaard moet
        # worden, ook als de feed leeg blijkt te zijn
        gewijzigd = not bekend
        nieuw: set[str] = set()

        for video in videos:
            video_id = video["video_id"]
            if video_id in bekend or not video["gepubliceerd"]:
                continue
            bekend[video_id] = {
                "titel": video["titel"],
                "url": video["url"],
                "thumbnail": video["thumbnail"],
                "gepubliceerd": video["gepubliceerd"].isoformat(),
            }
            nieuw.add(video_id)
            gewijzigd = True

        if self._begrens(channel_id):
            gewijzigd = True

        if gewijzigd:
            await self._async_save()
            if nieuw:
                _LOGGER.debug(
                    "%s nieuwe video('s) bewaard voor kanaal %s",
                    len(nieuw),
                    channel_id,
                )

        return nieuw

    def videos(self, channel_id: str) -> list[dict]:
        """Geef alle bewaarde video's van een kanaal, nieuwste eerst."""
        videos = [
            {
                "video_id": video_id,
                "titel": velden["titel"],
                "url": velden["url"],
                "thumbnail": velden["thumbnail"],
                "gepubliceerd": dt_util.parse_datetime(velden["gepubliceerd"]),
            }
            for video_id, velden in self._kanalen.get(channel_id, {}).items()
        ]
        videos.sort(
            key=lambda video: video["gepubliceerd"] or dt_util.utc_from_timestamp(0),
            reverse=True,
        )
        return videos

    async def async_remove_channel(self, channel_id: str) -> None:
        """Gooi het archief van een kanaal weg, bijvoorbeeld na verwijderen."""
        if self._kanalen.pop(channel_id, None) is not None:
            await self._async_save()
            _LOGGER.debug("Archief van kanaal %s verwijderd", channel_id)

    async def async_purge(self) -> None:
        """Ruim video's op die te oud zijn om nog mee te kunnen tellen."""
        grens = dt_util.utcnow() - timedelta(days=ARCHIVE_RETENTION_DAYS)
        gewijzigd = False

        for channel_id, bekend in self._kanalen.items():
            te_verwijderen = [
                video_id
                for video_id, velden in bekend.items()
                if _te_oud(velden.get("gepubliceerd"), grens)
            ]
            for video_id in te_verwijderen:
                del bekend[video_id]
            if te_verwijderen:
                gewijzigd = True
            if self._begrens(channel_id):
                gewijzigd = True

        if gewijzigd:
            await self._async_save()
            _LOGGER.debug("Archief opgeschoond")

    def _begrens(self, channel_id: str) -> bool:
        """Houd het aantal video's per kanaal onder de bovengrens."""
        bekend = self._kanalen.get(channel_id, {})
        if len(bekend) <= MAX_ARCHIVE_PER_CHANNEL:
            return False

        # Nieuwste eerst, daarna alles voorbij de grens weggooien
        op_datum = sorted(
            bekend, key=lambda video_id: _tijdstip(bekend[video_id]), reverse=True
        )
        for video_id in op_datum[MAX_ARCHIVE_PER_CHANNEL:]:
            del bekend[video_id]
        return True


def _tijdstip(velden: dict) -> datetime:
    """Geef de publicatiedatum van een opgeslagen video als datetime.

    Bewust niet op de opgeslagen tekst sorteren: "11:30+02:00" komt als tekst
    na "10:00+00:00", terwijl dat hetzelfde moment juist eerder is. YouTube
    stuurt op dit moment altijd +00:00, maar daar willen we niet van afhangen.
    """
    gepubliceerd = dt_util.parse_datetime(velden.get("gepubliceerd") or "")
    return gepubliceerd or dt_util.utc_from_timestamp(0)


def _te_oud(tijdstip: str | None, grens: datetime) -> bool:
    """Bepaal of een opgeslagen publicatiedatum voorbij de bewaartermijn is."""
    if not tijdstip:
        # Zonder leesbare datum kunnen we niets, dus opruimen
        return True
    gepubliceerd = dt_util.parse_datetime(tijdstip)
    return gepubliceerd is None or gepubliceerd < grens
