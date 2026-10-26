# utilities-perl-py

Python port of the Perl [`utilities-perl`](../utilities-perl) repository — a
collection of home-made utility libraries and small CLI scripts.

The port keeps the original behaviour where it is well defined and covered by
tests, while swapping Perl-specific machinery for the Python standard library
and a single third-party dependency (PyYAML). Perl-only test/scaffolding
infrastructure (`SH::UseLib`, `SH::ScriptX`/Applify, `Test::ScriptX`,
`SH::Test::Pod`, spell-checkers) is intentionally not ported — Python packaging
and `argparse` cover those needs.

## Install

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Library modules (Perl -> Python)

| Perl module | Python module | Notes |
| --- | --- | --- |
| `SH::PrettyPrint` | `utilities_perl.prettyprint` | `print_arrays`, `print_hashes`, `data_to_json_pretty`, `set_array_item` |
| `SH::CSVLastPass` | `utilities_perl.csv_lastpass` | `CSVLastPass.read` — handles quoted *and* unquoted multi-line fields |
| `SH::Email::ToHash` | `utilities_perl.email_to_hash` | `EmailToHash` — MIME text to nested dict |
| `SH::Ask` | `utilities_perl.ask` | `ask()` using stdin / `getpass` / `termios` |
| `SH::Alert` | `utilities_perl.alert` | `Alert.groupme` via GroupMe bot API (`urllib`) |
| `Model::GetCommonConfig` | `utilities_perl.config` | `GetCommonConfig` — Mojolicious/hypnotoad app config |
| `SH::PassCode`, `SH::PassCode::File` | `utilities_perl.passcode` | `PassCode`, `PassCodeFile` — wrap the external `pass`/`pass code` tool |
| `SH::Transform` | `utilities_perl.transform` | `Transform` + auto-selected importer/exporter plugins |
| `SH::Transform::Plugin::Importer::*` | `utilities_perl.transform.importers` | `JSONImporter`, `CSVLastPassImporter`, `SQLiteTableImporter` |
| `SH::Transform::Plugin::Exporter::*` | `utilities_perl.transform.exporters` | `YAMLExporter`, `PassCodeExporter` |

### Module/library swaps

| Perl dependency | Python replacement |
| --- | --- |
| `Module::Pluggable` | explicit plugin lists in `transform/__init__.py` |
| `Mojo::SQLite` | stdlib `sqlite3` |
| `Mojo::JSON` / `JSON` | stdlib `json` |
| `YAML::Syck` / `YAML::Tiny` | `PyYAML` |
| `Mojo::UserAgent` | stdlib `urllib.request` |
| `MIME::Base64` / `MIME::QuotedPrint` | stdlib `base64` / `quopri` |
| `Term::ReadKey` | stdlib `termios` / `tty` / `getpass` |
| `IPC::Run` / `IPC::Run3` | stdlib `subprocess` |

## CLI scripts (Perl `bin/*` -> console entry points)

| Perl script | Console command | Description |
| --- | --- | --- |
| `bin/alert.pl` | `alert` | Pipe text on stdin to send a GroupMe message |
| `bin/transform.pl` | `transform` | Read a source and write it to another format |
| `bin/dump-email-hash.pl` | `dump-email-hash` | Dump the parsed structure of an email file |
| `bin/file-forwarder.pl` | `file-forwarder` | Copy not-yet-copied files from source to destination dirs |
| `bin/file-rights-debug.pl` | `file-rights-debug` | Analyse why a file is not readable for a user |
| `bin/unixtid` | `unixtid` | Print current epoch, or convert an epoch to a datetime |
| `bin/b64d.sh` | `b64d` | base64-decode the first argument |
| `bin/winord` | `winord` | Tile/arrange windows via `wmctrl` (Linux/X11 only) |

Not ported: `bin/template.pl` and `SH::Code::Template*` (a Perl-source code
generator tied to the Applify/ScriptX framework), and the `git-*`/`prove-all`/
`spellchecker` developer helpers.

## rpg_common-pakken

Felles Python-logikk for `mm-rpg` og `osr-rpg`, portert fra Perl.
Pakken er installerbart via `uv` og eksponerer:

### Templatehjelpere (`rpg_common.template`)

Rene Python-funksjoner ment å *brukes i* Jinja2-maler (ikke Jinja2-filtre).
Funksjonene kalles fra malene for å generere tabeller, lister og sortering.

| Funksjon | Beskrivelse |
| --- | --- |
| `ctable(data, category, ...)` | Genererer Markdown-tabell fra en kategori med data |
| `clist(data, category, ...)` | Genererer norsk sammenkjedet liste (f.eks. "A, B og C") |
| `mytextsort(items, rekkefoelge)` | Sorterer nøkkelord etter definert rekkefølge |
| `myrowsort(data, rekkefoelge, ...)` | Sorterer rader etter kolonne eller rekkefølge |
| `gterning(number, offset, range_)` | Genererer terningområde-tekst (f.eks. "1-3") |
| `load_rekkefoelge(path)` | Laster `rekkefoelge.list.yml`-fil |

### YAML-til-tabell (`rpg_common.yaml_walk`)

| Funksjon | Beskrivelse |
| --- | --- |
| `get_tablename_keys_data(tablename, ret, data, ...)` | Rekursiv konvertering av nøstet YAML til relasjonelt skjema |

### Brukseksempel

```python
from rpg_common import ctable, clist, mytextsort, gterning

evner = [
    {"navn": "styrke", "pris": 2},
    {"navn": "sanse", "pris": 1},
    {"navn": "mana", "pris": 2},
]

# Sorter etter rekkefølge
rekkefoelge = ["styrke", "sanse", "mana"]
sortert = mytextsort([e["navn"] for e in evner], rekkefoelge)
# => ["styrke", "sanse", "mana"]

# Sammenkjedet liste
liste = clist(evner, "evner")
# => "styrke, sanse og mana"

# Markdown-tabell
tabell = ctable(evner, "evner", columns=["navn", "pris"])
# => |evner|pris|
#    |-|-|
#    |styrke|2|
#    |sanse|1|
#    |mana|2|

# Terningområde
offset, text = gterning(1, 1, 3)
# => (4, "1-3")
```

### Path-basert installasjon fra eksternt repo

```bash
# I mm-rpg eller osr-rpg:
uv run --script --with "utilities-perl-py @ file:///sti/til/utilities-py" skript.py
```

## Delbar pre-commit-hook (ruff)

Hooken gjør linting til en del av `git commit` i stedet for noe som først skjer
i review, og i stedet for en egen lint-test i pytest (menneskevedtak i sak #7).
Filen er portabel og kopieres uendret mellom Python-repoer. Kilde er dette
repoet (`utilities-py`).

### Dette kopieres

| Fil | Legges i | Merknad |
| --- | --- | --- |
| `hooks/pre-commit` | målrepoets `hooks/` | Kopieres **uendret**, uten repo-spesifikke tilpassinger |

### Slik tas filen i bruk

1. Kopier `hooks/pre-commit` til `hooks/pre-commit` i målrepoet og gjør den
   kjørbar: `chmod +x hooks/pre-commit`.
2. Aktiver hooken, for eksempel med `git config core.hooksPath hooks`.
   Alternativt kopieres filen til `.git/hooks/pre-commit`. Merk at
   `core.hooksPath` peker git bort fra `.git/hooks`, så eventuelle andre
   hooks der må flyttes med.
3. Legg `ruff` inn som dev-avhengighet, for eksempel `uv add --dev ruff`
   eller `uv add --optional dev ruff`. Uten dev-avhengighet brukes
   `uvx ruff` som fallback, og krever da `uvx` på `PATH`.
4. Ved neste commit kjøres sjekkene automatisk. Committen blokkeres ved
   avvik, med tydelig melding om hva som må fikses.

### Hva hooken sjekker

- `ruff check .` med ruff sitt standard regelsett (default)
- `ruff format --check .` for formatering

Feiler en av sjekkene, forteller feilmeldingen hva som må fikses:
`ruff check --fix` retter lint-varsel, `ruff format` retter formateringen.
Kjør deretter sjekken på nytt for å bekrefte at alt er rettet, og committen
på nytt.

Røyktester for hooken ligger i kilde-repoet (`tests/test_precommit_hook.py`)
og verifiserer blant annet at hooken feiler med tydelig melding på villet
lint- og formatfeil, blokkerer `git commit`, og håndterer manglende
ruff/uvx-fallback.

### Ruff-konfigurasjon

Hooken krever ingen medfølgende konfigurasjon: ruff kjører med default
(standard) oppsett, både regelsett og formatering (menneskevedtak i sak #7:
«Bruk standard» og «forsøk med default»). Egen `ruff.toml` eller
`[tool.ruff]`-blokk i målrepoet styrer i så fall nivået der, men standarden
er å ikke ha egen konfigurasjon.

### `# noqa` for regler utenfor standardregelsettet

Prinsippet er å **fjerne døde `# noqa`-er**, ikke å videreføre dem: merknader
som undertrykker regler standardregelsettet ikke håndhever (E501, PTH-, S-,
ARG-, PLC0415-regler og lignende) fjernes — både i dette repoet og i
målrepoer når gammel lint-konfigurasjon ryddes bort (se under). E501 (for
lange linjer) er en slik regel: den håndheves uansett ikke, og
`ruff format` bryter linjer der det trengs. Begrunnelsene bak slike døde
undertrykkelser beholdes som vanlige kommentarer eller docstring-notater, som
for `ARG001` i `rpg_common/template.py`.

`# noqa` som låser oppførsel som standardregelsettet ellers ville krevd
endret, beholdes med begrunnelse på samme linje. Det er den motsatte
kategorien av døde `# noqa`-er: regelen håndheves faktisk av
standardregelsettet, og oppførselen er tilsiktet. I dette repoet gjelder det
`# noqa: TRY004` (to steder) og `# noqa: BLE001` — TRY004 og BLE001 ligger i
ruff sitt default-regelsett (utvidet fra 59 til 413 regler i ruff 0.16), så
`ruff check .` feiler uten dem.

### Eksisterende lint-konfigurasjon i målrepoet

Meld fra om hva som fantes av lint-konfigurasjon i målrepoet før den
fjernes — for eksempel en `[tool.ruff]`-blokk i `pyproject.toml`, en eldre
`ruff.toml` eller et annet lint-oppsett. Notér funnet der det passer
(commit-melding, issue eller notat).

Deretter fjernes den gamle konfigurasjonen slik at default gjelder
(avklaring 8: meld fra og overskriv gammel konfig). Fjern for eksempel
`[tool.ruff]`-blokka i `pyproject.toml` og eventuell `ruff.toml`, slik at
det ikke ligger to konfigurasjoner som kjemper om hvilken som gjelder.

### Vedlikehold

Vedlikeholdet av hooken har agenten ansvar for. Mennesket justerer evt. hvor
aktivt den skal brukes (menneskevedtak i sak #7, svar 5).

## Design conventions

Carried over from `utilities-perl/AGENTS.md`:

- **Fail hard.** Raise with context on unexpected input rather than silently
  continuing. Perl `die` -> Python `raise`; the Perl yada (`...`) operator ->
  `raise NotImplementedError`.
- POD documentation -> module/function docstrings.
