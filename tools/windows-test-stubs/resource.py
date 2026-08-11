"""Vervanger voor de Unix-module resource, alleen om op Windows te kunnen testen.

Home Assistant gebruikt deze module om de limiet op het aantal open bestanden
op te hogen. Tijdens tests gebeurt dat niet; het gaat puur om de import die
anders mislukt. Zie fcntl.py in dezelfde map voor de toelichting.
"""

RLIMIT_CORE = 4
RLIMIT_NOFILE = 7
RLIM_INFINITY = -1


def getrlimit(resource_id):
    """Geef een geloofwaardige limiet terug."""
    return (1024, 4096)


def setrlimit(resource_id, limits):
    """Doe alsof de limiet is aangepast."""
    return None


def getrusage(who):
    """Geef een lege meting terug."""
    return (0.0,) * 16
