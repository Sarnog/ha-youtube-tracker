"""Ophalen en parsen van de publieke YouTube Atom-feed."""

from __future__ import annotations

import logging
import re
from urllib.parse import urlparse
from xml.etree.ElementTree import ParseError

import aiohttp
from defusedxml import ElementTree

from homeassistant.util import dt as dt_util

from .const import (
    CHANNEL_PAGE_URL,
    FEED_URL,
    FEED_URL_FALLBACK,
    NS,
    THUMBNAIL_URL,
    TOEGESTANE_HOSTS,
    VIDEO_URL,
)

_LOGGER = logging.getLogger(__name__)

# Een channel-ID is altijd "UC" gevolgd door 22 tekens
CHANNEL_ID_PATROON = re.compile(r"UC[\w-]{22}")
# In de HTML van een kanaalpagina staat het ID als "channelId":"UC..."
HTML_CHANNEL_ID_PATROON = re.compile(r'"channelId":"(UC[\w-]{22})"')


class FeedError(Exception):
    """Fout bij het ophalen of verwerken van de feed."""


def _controleer_host(url: str) -> None:
    """Weiger URL's die niet naar YouTube wijzen.

    Zonder deze controle zou Home Assistant een verzoek doen naar elk adres
    dat je in het configuratiescherm intypt.
    """
    host = (urlparse(url).hostname or "").lower()
    if host not in TOEGESTANE_HOSTS:
        raise FeedError(f"Alleen YouTube-URL's worden geaccepteerd, niet: {host}")


async def async_resolve_channel_id(session: aiohttp.ClientSession, invoer: str) -> str:
    """Zet gebruikersinvoer om naar een channel-ID.

    Geaccepteerd: een kaal UC-ID, een @handle, of een volledige kanaal-URL.
    """
    invoer = invoer.strip()

    # Staat er al een channel-ID in de invoer? Dan zijn we klaar.
    if (treffer := CHANNEL_ID_PATROON.search(invoer)) is not None:
        return treffer.group(0)

    # Bepaal het pad van de kanaalpagina dat we moeten opvragen
    if invoer.startswith("http"):
        _controleer_host(invoer)
        pad = invoer
    elif invoer.startswith("@"):
        pad = CHANNEL_PAGE_URL.format(invoer)
    else:
        pad = CHANNEL_PAGE_URL.format(f"@{invoer}")

    try:
        async with session.get(pad, timeout=aiohttp.ClientTimeout(total=20)) as reactie:
            if reactie.status != 200:
                raise FeedError(f"Kanaalpagina gaf status {reactie.status}")
            html = await reactie.text()
    except aiohttp.ClientError as fout:
        raise FeedError(f"Kanaalpagina niet bereikbaar: {fout}") from fout

    if (treffer := HTML_CHANNEL_ID_PATROON.search(html)) is not None:
        return treffer.group(1)

    raise FeedError("Geen channel-ID gevonden op de kanaalpagina")


async def async_fetch_feed(
    session: aiohttp.ClientSession, channel_id: str
) -> tuple[str, list[dict]]:
    """Haal de feed op en geef (kanaalnaam, lijst met video's) terug.

    Er wordt eerst geprobeerd de UULF-playlist op te halen; die bevat alleen
    normale uploads en dus geen Shorts. Levert dat niets op, dan valt de code
    terug op de gewone kanaalfeed.

    Een feed die goed binnenkomt maar geen video's bevat is geen fout: dat is
    gewoon een kanaal dat nog niets heeft geüpload.
    """
    uulf_id = channel_id.replace("UC", "UULF", 1)
    urls = [FEED_URL.format(uulf_id), FEED_URL_FALLBACK.format(channel_id)]

    laatste_fout: str | None = None
    kanaalnaam_leeg = ""
    feed_gelezen = False

    for url in urls:
        try:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=30)
            ) as reactie:
                if reactie.status != 200:
                    laatste_fout = f"Feed gaf status {reactie.status}"
                    continue
                xml = await reactie.text()
        except aiohttp.ClientError as fout:
            laatste_fout = f"Feed niet bereikbaar: {fout}"
            continue

        naam, videos = _parse_feed(xml)
        if videos:
            return naam, videos

        # Feed was leesbaar maar leeg; onthouden en de fallback proberen
        feed_gelezen = True
        kanaalnaam_leeg = naam or kanaalnaam_leeg

    if feed_gelezen:
        return kanaalnaam_leeg, []

    raise FeedError(laatste_fout or "Onbekende fout bij ophalen van de feed")


def _parse_feed(xml: str) -> tuple[str, list[dict]]:
    """Verwerk de Atom-XML naar een kanaalnaam en een lijst met video's."""
    try:
        wortel = ElementTree.fromstring(xml)
    except (ParseError, ValueError) as fout:
        raise FeedError(f"Feed kon niet worden gelezen: {fout}") from fout

    # Kanaalnaam staat in het author-element van de feed zelf
    naam_element = wortel.find("atom:author/atom:name", NS)
    kanaalnaam = naam_element.text if naam_element is not None else ""
    if not kanaalnaam:
        titel_element = wortel.find("atom:title", NS)
        kanaalnaam = titel_element.text if titel_element is not None else "YouTube"

    videos: list[dict] = []
    for item in wortel.findall("atom:entry", NS):
        video_id_element = item.find("yt:videoId", NS)
        titel_element = item.find("atom:title", NS)
        datum_element = item.find("atom:published", NS)

        if video_id_element is None or not video_id_element.text:
            continue

        video_id = video_id_element.text
        gepubliceerd = None
        if datum_element is not None and datum_element.text:
            gepubliceerd = dt_util.parse_datetime(datum_element.text)

        # Thumbnail uit media:group halen, met een vaste URL als terugval
        thumbnail_element = item.find("media:group/media:thumbnail", NS)
        thumbnail = (
            thumbnail_element.get("url")
            if thumbnail_element is not None
            else THUMBNAIL_URL.format(video_id)
        )

        videos.append(
            {
                "video_id": video_id,
                "titel": (titel_element.text or "").strip()
                if titel_element is not None
                else "",
                "url": VIDEO_URL.format(video_id),
                "thumbnail": thumbnail,
                "gepubliceerd": gepubliceerd,
            }
        )

    # Nieuwste video's bovenaan
    videos.sort(
        key=lambda video: video["gepubliceerd"] or dt_util.utc_from_timestamp(0),
        reverse=True,
    )
    return kanaalnaam, videos
