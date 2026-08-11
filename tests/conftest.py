"""Gedeelde instellingen en hulpstukken voor alle tests."""

from __future__ import annotations

import pathlib
import sys

import pytest

# Laadt de Home Assistant-testomgeving (nep-hass, fixtures, enzovoort)
pytest_plugins = "pytest_homeassistant_custom_component"

FIXTURE_MAP = pathlib.Path(__file__).parent / "fixtures"

WINDOWS = sys.platform == "win32"

# De testomgeving blokkeert netwerkverkeer en maakt daarbij een uitzondering
# voor Unix-sockets, omdat asyncio die nodig heeft om zijn eigen event loop
# wakker te maken. Windows kent geen Unix-sockets: daar valt Python terug op
# een gewone TCP-verbinding met zichzelf, en die wordt dus geweigerd - nog
# voordat er ook maar een test is gestart.
#
# Op Windows maken we de blokkade daarom onschadelijk. Dat kan hier, op
# moduleniveau, omdat conftest.py wordt ingelezen voordat de testomgeving de
# blokkade aanzet. De HTTP-verzoeken in de tests worden sowieso opgevangen
# door aioclient_mock, dus er gaat niets echt de deur uit.
#
# Op Linux, en dus in GitHub Actions, blijft de blokkade gewoon staan. Daar
# draait de echte controle.
if WINDOWS:
    import pytest_socket

    pytest_socket.disable_socket = lambda *args, **kwargs: None


@pytest.fixture(autouse=True)
def sta_custom_integrations_toe(enable_custom_integrations):
    """Geef Home Assistant toestemming om onze eigen integratie te laden.

    Zonder deze fixture weigert de testomgeving alles in custom_components.
    Hij staat op autouse, zodat geen enkele test hem hoeft aan te vragen.
    """
    return


@pytest.fixture
def lees_fixture():
    """Geef een functie terug die een bestand uit tests/fixtures inleest."""

    def _lees(bestandsnaam: str) -> str:
        return (FIXTURE_MAP / bestandsnaam).read_text(encoding="utf-8")

    return _lees
