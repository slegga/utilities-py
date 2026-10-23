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

## Sjekkeskript for lint-tester (`scripts/sjekk-lint-tester.py`)

Skriptet går gjennom alle repoene i prosjektet og sjekker at de delbare
lint-testene er på plass og i tråd med standarden. Det er et uv-skript
(PEP 723) og kjøres direkte:

```bash
./scripts/sjekk-lint-tester.py
```

På systemer med `coreutils` eldre enn 8.30 (uten `env -S`): `uv run --script
scripts/sjekk-lint-tester.py`. Skriptet trenger ingen installasjon — uv
løser avhengighetene (PyYAML, tomli) automatisk. Et kort
[arkitekturnotat](docs/sjekk-lint-tester.md) ligger i `docs/`.

### Hvordan skriptet finner repoene

Uten argumenter leses `config.yaml` i meta-privat: `repogruppe` peker på
repolista (for eksempel `repos-all.txt` — ett reponavn per linje,
`#`-linjer hoppes over) og `repos_dir` sier hvor repoene ligger.
Meta-privat finnes med `--meta-rot`, miljøvariabelen `META_PRIVAT_ROT`
eller ved å søke oppover fra skriptet og fra arbeidskatalogen. Med
`--repo-rot` og/eller `--repo-liste` kjøres skriptet mot en annen rot
eller liste — for eksempel mot et fikstur-tre i testene.

### Statusverdier og exit-kode

| Status | Betydning |
| --- | --- |
| `OK` | Lint-testen er på plass, inngår i den lokale testkjøringen og følger standarden |
| `mangler` | Lint-testen (`tests/test_lint.py` for Python, `tests/lint.rs` for Rust) finnes ikke |
| `avvik` | Lint-testen finnes, men noe avviker: den inngår ikke i den lokale testkjøringen, innholdet avviker fra referansefilen, eller lint-konfigurasjonen er ikke standarden |
| `intet å gjøre` | Repoet har ingen kode (verken Python eller Rust) |
| `ikke klonet` | Repo-katalogen finnes ikke lokalt; telles i sammendraget, men påvirker ikke exit-koden |

Exit-kode `0` betyr alt OK. Ikke-null exit-kode betyr avvik (eller at
sjekkene ikke kunne fullføres): `1` når minst ett repo har `mangler`
eller `avvik`, `2` når skriptet ikke kunne fullføre alle sjekkene (fant
ikke repolista, eller referansefilene fra sak #2/sak #8 mangler). Dette
gjør skriptet egnet for automatiserte kontroller.

### Fiks-kommandoene

Skriptet endrer aldri repoene selv (avklaring 5) — for hvert avvik skriver
det ut konkrete kommandoer som du kopierer og kjører selv:

* **Kopiering av testfiler:** `cp`-kommandoer som kopierer
  `tests/test_lint.py` (fra `utilities-py`) og `tests/lint.rs` (fra
  `personlig-py`) inn i målrepoets testkatalog uten endringer (avklaring 4).
  Den delbare testfilen skal ikke tilpasses det enkelte repoet — den finner
  prosjektroten relativt til seg selv.
* **Overskriving av gammel lint-konfigurasjon med standarden** (avklaring 8):
  `cp` av standard `ruff.toml` fra `utilities-py`, fjerning av
  overskrivende konfig-filer (`.ruff.toml`, `clippy.toml`, `rustfmt.toml`
  med flere) og kommandoer som fjerner `[tool.ruff]`-seksjoner fra
  `pyproject.toml` og `[lints]`-innstillinger fra `Cargo.toml`. Skriptet
  skriver ut dagens innhold først, slik at avvikende konfigurasjon kan
  vurderes før den overskrives.

### Klassifisering og sjekk av lokal testkjøring

Hvert repo klassifiseres som **Python**, **Rust**, **begge deler** eller
**ingen kode** ut fra `pyproject.toml`/`*.py` og `Cargo.toml`/`*.rs`.
Repoer med begge deler sjekkes for begge lint-testene.

For Python sjekkes det at `tests/test_lint.py` (eventuelt `test/`) ville
blitt samlet inn av pytest, ut fra repoets `testpaths` og `python_files`
i pytest-oppsettet. For Rust sjekkes det at `tests/lint.rs` kjøres av
`cargo test` — som integrasjonstest under `tests/` eller via et eksplisitt
`[[test]]`-mål i `Cargo.toml`.

## Design conventions

Carried over from `utilities-perl/AGENTS.md`:

- **Fail hard.** Raise with context on unexpected input rather than silently
  continuing. Perl `die` -> Python `raise`; the Perl yada (`...`) operator ->
  `raise NotImplementedError`.
- POD documentation -> module/function docstrings.
