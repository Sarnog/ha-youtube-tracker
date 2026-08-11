"""HTTP-endpoint dat een video als bekeken markeert en doorstuurt."""

from __future__ import annotations

import logging
import re

from aiohttp import web

from homeassistant.components.http import HomeAssistantView

from .const import QUERY_OPEN, VIDEO_URL, VIEW_URL
from .store import WatchedStore

_LOGGER = logging.getLogger(__name__)

# Een YouTube video-ID is precies 11 tekens uit deze set. Bewust geen
# isalnum(): dat accepteert ook Unicode-cijfers en letters met accenten.
VIDEO_ID_PATROON = re.compile(r"[A-Za-z0-9_-]{11}")


class YouTubeWatchView(HomeAssistantView):
    """Markeert een video als bekeken en stuurt de browser door naar YouTube.

    Zo is één klik op het dashboard genoeg: de video opent en de teller loopt
    meteen terug. Er is geen login nodig, want de link moet ook werken vanuit
    een notificatie. In plaats daarvan zit er per video een handtekening in de
    URL, die alleen Home Assistant kan maken.
    """

    url = VIEW_URL
    name = "api:youtube_tracker:watch"
    requires_auth = False

    def __init__(self, store: WatchedStore) -> None:
        """Initialiseer de view."""
        self._store = store

    async def get(
        self, request: web.Request, video_id: str, signature: str
    ) -> web.Response:
        """Verwerk de klik: markeer de video, en open hem eventueel."""
        if not VIDEO_ID_PATROON.fullmatch(video_id):
            return web.Response(status=400, text="Ongeldig video-ID")

        if not self._store.controleer_handtekening(video_id, signature):
            _LOGGER.debug("Ongeldige handtekening voor video %s", video_id)
            return web.Response(status=404, text="Niet gevonden")

        await self._store.async_mark(video_id)
        _LOGGER.debug("Video %s gemarkeerd via kijk-link", video_id)

        if request.query.get(QUERY_OPEN) == "0":
            # Een leeg antwoord met status 204 laat de browser staan waar hij
            # staat. Zo werkt de link als een afvink-knop op je dashboard: de
            # sensor verandert en de kaart werkt zichzelf bij.
            return web.Response(status=204)

        raise web.HTTPFound(VIDEO_URL.format(video_id))
