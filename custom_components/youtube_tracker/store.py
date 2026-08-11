"""Persistente opslag van bekeken video's."""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import secrets
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    SIGNAL_WATCHED_UPDATED,
    SIGNATURE_LENGTH,
    STORAGE_KEY,
    STORAGE_SECRET_KEY,
    STORAGE_VERSION,
    WATCHED_RETENTION_DAYS,
)

_LOGGER = logging.getLogger(__name__)


class WatchedStore:
    """Houdt bij welke video's al bekeken zijn. Overleeft een herstart."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialiseer de opslag."""
        self.hass = hass
        self._store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        # Structuur: {"video_id": "ISO-tijdstip waarop gemarkeerd"}
        self._watched: dict[str, str] = {}
        # Geheim voor de handtekeningen in de kijk-URL. Blijft in .storage en
        # komt nooit in een sensor-attribuut of in de database terecht.
        self._geheim: str = ""

    async def async_load(self) -> None:
        """Laad de opgeslagen gegevens van schijf."""
        data = await self._store.async_load() or {}
        self._watched = data.get("watched", {})
        self._geheim = data.get(STORAGE_SECRET_KEY, "")

        # Genereer het geheim eenmalig, bij de allereerste start
        if not self._geheim:
            self._geheim = secrets.token_urlsafe(32)
            await self._async_save()

        await self.async_purge()

    async def _async_save(self) -> None:
        """Schrijf de gegevens weg naar schijf."""
        await self._store.async_save(
            {"watched": self._watched, STORAGE_SECRET_KEY: self._geheim}
        )

    def maak_handtekening(self, video_id: str) -> str:
        """Maak een code die alleen voor deze ene video geldig is.

        Dit is een HMAC: uit het geheim en het video-ID rolt een korte code die
        je niet kunt namaken zonder het geheim. Omdat het video-ID meedoet in de
        berekening, geeft elke video een andere code. Wie de code van video A
        onderschept, kan daarmee dus niets met video B.
        """
        ruw = hmac.new(
            self._geheim.encode(), video_id.encode(), hashlib.sha256
        ).digest()
        return base64.urlsafe_b64encode(ruw).decode()[:SIGNATURE_LENGTH]

    def controleer_handtekening(self, video_id: str, handtekening: str) -> bool:
        """Controleer of een handtekening bij dit video-ID hoort."""
        if not self._geheim:
            return False
        # compare_digest vergelijkt in constante tijd, zodat je niet uit de
        # reactietijd kunt afleiden hoeveel tekens je goed had
        return hmac.compare_digest(handtekening, self.maak_handtekening(video_id))

    def is_watched(self, video_id: str) -> bool:
        """Controleer of een video al bekeken is."""
        return video_id in self._watched

    async def async_mark(self, video_ids: str | list[str]) -> int:
        """Markeer een of meerdere video's als bekeken."""
        if isinstance(video_ids, str):
            video_ids = [video_ids]

        nu = dt_util.utcnow().isoformat()
        gewijzigd = 0
        for video_id in video_ids:
            if video_id and video_id not in self._watched:
                self._watched[video_id] = nu
                gewijzigd += 1

        if gewijzigd:
            await self._async_save()
            async_dispatcher_send(self.hass, SIGNAL_WATCHED_UPDATED)
            _LOGGER.debug("%s video('s) als bekeken gemarkeerd", gewijzigd)
        return gewijzigd

    async def async_unmark(self, video_ids: str | list[str]) -> int:
        """Zet een of meerdere video's terug op ongezien."""
        if isinstance(video_ids, str):
            video_ids = [video_ids]

        gewijzigd = 0
        for video_id in video_ids:
            if self._watched.pop(video_id, None) is not None:
                gewijzigd += 1

        if gewijzigd:
            await self._async_save()
            async_dispatcher_send(self.hass, SIGNAL_WATCHED_UPDATED)
        return gewijzigd

    async def async_purge(self) -> None:
        """Ruim markeringen op die ouder zijn dan de bewaartermijn."""
        grens = dt_util.utcnow() - timedelta(days=WATCHED_RETENTION_DAYS)
        te_verwijderen = []

        for video_id, tijdstip in self._watched.items():
            gemarkeerd_op = dt_util.parse_datetime(tijdstip)
            # Onleesbare tijdstippen ook opruimen
            if gemarkeerd_op is None or gemarkeerd_op < grens:
                te_verwijderen.append(video_id)

        if te_verwijderen:
            for video_id in te_verwijderen:
                self._watched.pop(video_id, None)
            await self._async_save()
            _LOGGER.debug("%s oude markering(en) opgeruimd", len(te_verwijderen))
