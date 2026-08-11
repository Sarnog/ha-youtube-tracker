  <a href="#nl">NL</a> | <a href="#en">EN</a>

# Tests draaien op Windows

##### <ins>NL</ins>

Home Assistant ondersteunt Windows niet meer. De testomgeving importeert twee
Unix-modules die daar niet bestaan, `fcntl` en `resource`, en klapt daarop nog
voordat er een test is gestart.

De twee bestanden in deze map zijn lege vervangers voor die modules. Ze doen
niets: de functies erin worden tijdens tests nooit echt aangeroepen, want Home
Assistant gebruikt ze alleen bij het daadwerkelijk opstarten.

Je zet ze in gebruik door de map aan `PYTHONPATH` toe te voegen:

```powershell
# PowerShell
$env:PYTHONPATH = "tools\windows-test-stubs"
.venv\Scripts\python.exe -m pytest
```

```bash
# Git Bash
PYTHONPATH=tools/windows-test-stubs .venv/Scripts/python.exe -m pytest
```

Daarnaast zet `tests/conftest.py` op Windows de socketblokkade van de
testomgeving uit. Die blokkade laat Unix-sockets door omdat asyncio ze nodig
heeft; op Windows valt Python terug op een TCP-verbinding met zichzelf, en die
wordt dan geweigerd.

**Let op:** dit is een hulpmiddel om lokaal snel te kunnen testen, geen
vervanging voor de echte controle. Die draait in GitHub Actions op Linux,
zonder een van deze omwegen. Slaagt iets lokaal maar faalt het in de Actions,
dan heeft de Actions gelijk.


---



##### <ins>EN</ins>

Home Assistant no longer supports Windows. Its test environment imports two
Unix modules that do not exist there, `fcntl` and `resource`, and crashes on
that before a single test has started.

The two files in this folder are empty stand-ins for those modules. They do
nothing: the functions in them are never actually called during tests, because
Home Assistant only uses them when genuinely starting up.

Put them to use by adding this folder to `PYTHONPATH`:

```powershell
# PowerShell
$env:PYTHONPATH = "tools\windows-test-stubs"
.venv\Scripts\python.exe -m pytest
```

```bash
# Git Bash
PYTHONPATH=tools/windows-test-stubs .venv/Scripts/python.exe -m pytest
```

On top of that, `tests/conftest.py` disables the test environment's socket
blocking on Windows. That blocking lets Unix sockets through because asyncio
needs them; on Windows Python falls back to a TCP connection to itself, which
then gets refused.

**Note:** this is a convenience for testing locally, not a replacement for the
real check. That one runs in GitHub Actions on Linux, without any of these
detours. If something passes locally but fails in Actions, Actions is right.
