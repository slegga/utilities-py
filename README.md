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

## Sjekkeskript for linting (`scripts/sjekk-lint-tester.py`)

Skriptet går gjennom alle repoene i prosjektet og sjekker at linting er på
plass i tråd med standarden. Det er et uv-skript (PEP 723) og kjøres direkte:

```bash
./scripts/sjekk-lint-tester.py
```

På systemer med `coreutils` eldre enn 8.30 (uten `env -S`): `uv run --script
scripts/sjekk-lint-tester.py`. Skriptet trenger ingen installasjon — uv
løser avhengighetene (tomli) automatisk. Et kort
[arkitekturnotat](docs/sjekk-lint-tester.md) ligger i `docs/`.

### Hvordan skriptet finner repoene

Repoene er alle underkataloger ett nivå under meta-privat
(menneskevedtak i sak #11: «Trenger ikke repo liste, bruk et nivå av
kataloger i meta-privat som definisjon»). Ingen repo-liste leses lenger —
`config.yaml`, `repogruppe` og `repos-all.txt` brukes ikke av skriptet.
Skjulte kataloger og byggeartefakter (`__pycache__`, `.venv`, `target`
med flere) hoppes over. Roten er `~/meta-privat`, og kan overstyres med
`--repo-rot` eller miljøvariabelen `META_PRIVAT_ROT` — for eksempel mot
et fikstur-tre i testene. Også meta-privats egne underkataloger (`tests/`,
`docs/`, `scripts/`) tas med: pre-commit-hooken tilhører git-repoet som
eier katalogen, og for dem er det meta-privat selv.

### Statusverdier og exit-kode

| Status | Betydning |
| --- | --- |
| `OK` | Linting er på plass og følger standarden |
| `mangler` | Pre-commit-hooken (Python) eller `tests/lint.rs` (Rust) finnes ikke |
| `avvik` | Noe finnes, men avviker: hooken er ikke aktivert/kjørbar eller er ikke referansekopien, gammel lint-test henger igjen, eller lint-konfigurasjonen er ikke standarden |
| `intet å gjøre` | Katalogen har ingen kode (verken Python eller Rust) |

Exit-kode `0` betyr alt OK. `1` betyr at minst ett repo har `mangler`
eller `avvik` — **reelle avvik vinner over exit-kode 2**, slik at manglende
referansefiler ikke maskerer avvik som faktisk er funnet. `2` betyr at
ingen reelle avvik ble funnet, men at skriptet ikke kunne fullføre alle
sjekkene (fant ikke meta-privat, eller referansefilene fra sak #2/sak #8
mangler). Dette gjør skriptet egnet for automatiserte kontroller.

Utskrift er fritekst per repo. `--json` gir den samme rapporten som ett
maskinlesbart JSON-dokument (`repo_rot`, `referanser`, `repoer` med funn og
fiks-kommandoer, `sammendrag` og `exit_kode`) for automatiserte kontroller.
Ved fatale feil (finner ikke repo-rota) skrives feilmeldingen til stderr
med exit-kode 2, også med `--json`.

### Fiks-kommandoene

Skriptet endrer aldri repoene selv (avklaring 5) — for hvert avvik skriver
det ut konkrete kommandoer som du kopierer og kjører selv:

* **Installasjon og aktivering av pre-commit-hooken:** `cp` av
  `hooks/pre-commit` (fra `utilities-py`) inn i målrepoet uten endringer
  (avklaring 4), `chmod +x` og `git config core.hooksPath hooks`.
* **Fjerning av gammel lint-test:** `rm` av `tests/test_lint.py` — linting
  for Python skjer via pre-commit-hooken, ikke i testkjøringen
  (menneskevedtak i sak #7 og #11).
* **Kopiering av Rust-lint-testen:** `cp` av `tests/lint.rs` (fra
  `personlig-py`) inn i målrepoets testkatalog uten endringer (avklaring 4).
* **Overskriving av gammel lint-konfigurasjon med standarden** (avklaring 8):
  fjerning av `ruff.toml`/`.ruff.toml`, `[tool.ruff]`-seksjoner fra
  `pyproject.toml` og `[lints]`-innstillinger fra `Cargo.toml`, samt
  `clippy.toml`/`rustfmt.toml`-varianter. Skriptet skriver ut dagens innhold
  først, slik at avvikende konfigurasjon kan vurderes før den overskrives.
  Finnes flere ruff-konfigurasjoner samtidig, beholdes én (den første
  standardkonfigurasjonen) og fiks-kommandoene fjerner de overskytende —
  også når hver av dem for seg er standard.
  To tilfeller krever eksplisitt avklaring med mennesket før
  fiks-kommandoen kjøres (sak #14): en hook med markdownlint/cspell
  (overskriving fjerner stave- og markdown-kontrollen) og en
  `exclude`-innstilling i ruff-konfigurasjonen (for eksempel
  `exclude = ["old"]` i investment-oslo — fjerning gjør at arkivert kode
  blir lintet). Skriptet varsler eksplisitt i begge tilfellene.

### Lint-konfigurasjonen og E501

Standarden er ruff **default** regelsett uten egen konfigurasjon
(menneskevedtak i sak #7: «Bruk standard», «forsøk med default»). Det
eneste tillatte tillegget er E501-unntaket (menneskevedtak i sak #11:
«Ignore E501 skal videre føres overalt»):

* Default-regelsettet håndhever ikke E501 (linjer for lange), så E501 er
  ignorert overalt så lenge default gjelder.
* Fiks-kommandoene **bevarer eksplisitte E501-unntak** der de finnes, for
  eksempel `ignore = ["E501"]` i `[tool.ruff.lint]`. Et slikt unntak skrives
  tilbake som eneste gjenværende innstilling når gammel konfig ryddes bort.

Slik blir det ikke to standarder som står mot hverandre: enten default,
eller default med E501-unntaket skrevet ut eksplisitt.

### Klassifisering og hva som sjekkes

Hvert repo klassifiseres som **Python**, **Rust**, **begge deler** eller
**ingen kode** ut fra `pyproject.toml`/`*.py` og `Cargo.toml`/`*.rs`.
Repoer med begge deler sjekkes for begge delene.

For Python sjekkes det at linting skjer via en **git pre-commit-hook**:
hooken skal være aktivert (`core.hooksPath` på alle git-konfig-nivåer,
ellers `.git/hooks/pre-commit`),
være kjørbar, kjøre `ruff` og være referansefilen kopiert uendret
(avklaring 4). Innholdet vurderes mot referansen også når hooken finnes
uten å være aktivert: en hook som ikke driver Python-linting (for eksempel
en markdownlint-hook) skal overskrives med referansekopien, ikke bare
aktiveres. Den gamle lint-testen `tests/test_lint.py` skal være fjernet
— linting skal ikke lenger skje i testkjøringen. For Rust sjekkes det
fortsatt at `tests/lint.rs` er på plass, er referansefilen kopiert uendret
og kjøres av `cargo test` — som integrasjonstest under `tests/` eller via
et eksplisitt `[[test]]`-mål i `Cargo.toml`. Pre-commit-hooken gjelder
Python-lintingen; Rust-repoer beholder lintingen i `cargo test`
(personlig-py sak #8: leveransen «står foreløpig uendret»).

### Vedlikehold

Vedlikeholdet av skriptet har agenten ansvar for. Mennesket justerer evt.
hvor aktivt det skal brukes (menneskevedtak i sak #7, svar 5).

## Design conventions

Carried over from `utilities-perl/AGENTS.md`:

- **Fail hard.** Raise with context on unexpected input rather than silently
  continuing. Perl `die` -> Python `raise`; the Perl yada (`...`) operator ->
  `raise NotImplementedError`.
- POD documentation -> module/function docstrings.
