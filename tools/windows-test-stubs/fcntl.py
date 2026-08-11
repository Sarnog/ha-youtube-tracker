"""Vervanger voor de Unix-module fcntl, alleen om op Windows te kunnen testen.

Home Assistant ondersteunt Windows niet meer en importeert bovenaan runner.py
de module fcntl. Die bestaat op Windows niet, waardoor de testomgeving al bij
het opstarten klapt. De functies hieronder worden tijdens tests nooit echt
aangeroepen: Home Assistant gebruikt ze alleen bij het daadwerkelijk starten,
om een lockfile te pakken.

Zie tools/windows-test-stubs/README.md voor het gebruik. Op Linux, en dus in
GitHub Actions, wordt dit bestand niet aangeraakt.
"""

LOCK_SH = 1
LOCK_EX = 2
LOCK_NB = 4
LOCK_UN = 8

F_GETFD = 1
F_SETFD = 2
F_GETFL = 3
F_SETFL = 4


def flock(fd, operation):
    """Doe alsof het bestand vergrendeld is."""
    return None


def lockf(fd, operation, length=0, start=0, whence=0):
    """Doe alsof het bestandsdeel vergrendeld is."""
    return None


def fcntl(fd, cmd, arg=0):
    """Doe alsof de bestandsoptie is aangepast."""
    return 0


def ioctl(fd, request, arg=0, mutate_flag=True):
    """Doe alsof de apparaatoptie is aangepast."""
    return 0
