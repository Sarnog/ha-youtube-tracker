"""Tests voor de peildatum, oftewel vanaf wanneer een video meetelt."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from homeassistant.core import HomeAssistant

from custom_components.youtube_tracker.const import MODE_DAGEN, MODE_VORIGE_MAAND
from custom_components.youtube_tracker.coordinator import bereken_peildatum

AMSTERDAM = ZoneInfo("Europe/Amsterdam")


@pytest.fixture
async def nederlandse_tijd(hass: HomeAssistant):
    """Zet de tijdzone van Home Assistant op Amsterdam."""
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    return hass


# --- Modus "begin van de vorige maand" --------------------------------------


async def test_vorige_maand_binnen_hetzelfde_jaar(nederlandse_tijd, freezer):
    """Sta je in augustus, dan is de peildatum 1 juli."""
    freezer.move_to("2026-08-10 09:00:00+00:00")

    peildatum = bereken_peildatum(MODE_VORIGE_MAAND, 30)

    assert peildatum.astimezone(AMSTERDAM).replace(tzinfo=None) == datetime(
        2026, 7, 1, 0, 0
    )


async def test_vorige_maand_over_de_jaargrens(nederlandse_tijd, freezer):
    """Sta je in januari, dan is de peildatum 1 december van het jaar ervoor."""
    freezer.move_to("2026-01-15 12:00:00+00:00")

    peildatum = bereken_peildatum(MODE_VORIGE_MAAND, 30)

    assert peildatum.astimezone(AMSTERDAM).replace(tzinfo=None) == datetime(
        2025, 12, 1, 0, 0
    )


async def test_vorige_maand_op_de_eerste_van_de_maand(nederlandse_tijd, freezer):
    """Ook op de 1e zelf hoort de peildatum een maand terug te liggen."""
    freezer.move_to("2026-03-01 08:00:00+00:00")

    peildatum = bereken_peildatum(MODE_VORIGE_MAAND, 30)

    assert peildatum.astimezone(AMSTERDAM).replace(tzinfo=None) == datetime(
        2026, 2, 1, 0, 0
    )


async def test_vorige_maand_na_een_korte_februari(nederlandse_tijd, freezer):
    """Vanuit maart terugrekenen mag niet stranden op 28 of 29 dagen."""
    freezer.move_to("2026-03-31 12:00:00+00:00")

    peildatum = bereken_peildatum(MODE_VORIGE_MAAND, 30)

    assert peildatum.astimezone(AMSTERDAM).replace(tzinfo=None) == datetime(
        2026, 2, 1, 0, 0
    )


async def test_de_nederlandse_datum_bepaalt_de_maand(nederlandse_tijd, freezer):
    """Het gaat om de datum bij ons, niet om de datum in UTC.

    Op 31 maart 23:00 UTC is het in Nederland al 1 april. De vorige maand is
    dan maart, niet februari.
    """
    freezer.move_to("2026-03-31 23:00:00+00:00")

    peildatum = bereken_peildatum(MODE_VORIGE_MAAND, 30)

    assert peildatum.astimezone(AMSTERDAM).replace(tzinfo=None) == datetime(
        2026, 3, 1, 0, 0
    )


# --- De tijdzone, oftewel waar het eerder misging ---------------------------


async def test_peildatum_is_middernacht_in_zomertijd(nederlandse_tijd, freezer):
    """In de zomer loopt Nederland twee uur voor op UTC.

    De peildatum hoort dus op 30 juni 22:00 UTC te liggen, want dat is
    1 juli middernacht bij ons. Eerder werd hier 1 juli 00:00 UTC van gemaakt,
    en dat is twee uur te laat.
    """
    freezer.move_to("2026-08-10 09:00:00+00:00")

    peildatum = bereken_peildatum(MODE_VORIGE_MAAND, 30)

    assert peildatum.isoformat() == "2026-06-30T22:00:00+00:00"


async def test_peildatum_is_middernacht_in_wintertijd(nederlandse_tijd, freezer):
    """In de winter is het verschil een uur in plaats van twee."""
    freezer.move_to("2026-01-15 12:00:00+00:00")

    peildatum = bereken_peildatum(MODE_VORIGE_MAAND, 30)

    assert peildatum.isoformat() == "2025-11-30T23:00:00+00:00"


async def test_video_vlak_na_middernacht_telt_mee(nederlandse_tijd, freezer):
    """Dit is de bug die we hebben gerepareerd.

    Een video van 1 juli 00:30 Nederlandse tijd viel er eerst net buiten,
    omdat de peildatum in UTC werd berekend.
    """
    freezer.move_to("2026-08-10 09:00:00+00:00")
    peildatum = bereken_peildatum(MODE_VORIGE_MAAND, 30)

    vlak_na_middernacht = datetime(2026, 7, 1, 0, 30, tzinfo=AMSTERDAM)

    assert vlak_na_middernacht >= peildatum


async def test_video_vlak_voor_middernacht_telt_niet_mee(nederlandse_tijd, freezer):
    """De grens moet wel een grens blijven: 30 juni hoort er niet bij."""
    freezer.move_to("2026-08-10 09:00:00+00:00")
    peildatum = bereken_peildatum(MODE_VORIGE_MAAND, 30)

    vlak_voor_middernacht = datetime(2026, 6, 30, 23, 30, tzinfo=AMSTERDAM)

    assert vlak_voor_middernacht < peildatum


# --- Modus "aantal dagen terug" ---------------------------------------------


async def test_aantal_dagen_terug(nederlandse_tijd, freezer):
    """De dagen-modus is een rollend venster vanaf nu, niet vanaf middernacht."""
    freezer.move_to("2026-08-10 09:00:00+00:00")

    peildatum = bereken_peildatum(MODE_DAGEN, 30)

    assert peildatum.isoformat() == "2026-07-11T09:00:00+00:00"


async def test_aantal_dagen_negeert_de_maandmodus(nederlandse_tijd, freezer):
    """Het aantal dagen telt alleen in de dagen-modus."""
    freezer.move_to("2026-08-10 09:00:00+00:00")

    per_maand = bereken_peildatum(MODE_VORIGE_MAAND, 999)
    per_dagen = bereken_peildatum(MODE_DAGEN, 999)

    assert per_maand != per_dagen
    assert per_maand.astimezone(AMSTERDAM).day == 1


async def test_peildatum_is_altijd_in_utc(nederlandse_tijd, freezer):
    """Beide modi geven UTC terug, zodat vergelijken met de feed klopt."""
    freezer.move_to("2026-08-10 09:00:00+00:00")

    for modus in (MODE_VORIGE_MAAND, MODE_DAGEN):
        peildatum = bereken_peildatum(modus, 30)
        assert peildatum.tzinfo is not None
        assert peildatum.utcoffset().total_seconds() == 0
