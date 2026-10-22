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

## Delbar lint-test (ruff)

Lint-testen gjør linting til en del av de lokale testene i stedet for noe som
først skjer i review og commit. Filen er portabel og kopieres uendret mellom
Python-repoer. Kilde er dette repoet (`utilities-py`).

### Dette kopieres

| Fil | Legges i | Merknad |
| --- | --- | --- |
| `tests/test_lint.py` | målrepoets testkatalog (`tests/` eller `test/`) | Kopieres **uendret**, uten repo-spesifikke tilpassinger |
| `ruff.toml` | målrepoets rot | Standard ruff-konfigurasjon som følger testen |

### Slik tas filen i bruk

1. Kopier `tests/test_lint.py` til testkatalogen (`tests/` eller `test/`).
2. Kopier `ruff.toml` til rotkatalogen i repoet.
3. Legg `ruff` inn som dev-avhengighet, for eksempel `uv add --dev ruff`
   eller `uv add --optional dev ruff`. Uten dev-avhengighet brukes
   `uvx ruff` som fallback, og krever da `uvx` på `PATH`.
4. Kjør testene slik du ellers gjør — lint-testen inngår da i den lokale
   testkjøringen:

   ```bash
   uv run --with pytest pytest
   ```

### Hva testen sjekker

- `ruff check .` med bredt regelsett (styrt av `select`/`ignore` i `ruff.toml`)
- `ruff format --check .` for formatering

Feiler en av sjekkene, forteller feilmeldingen hva som må fikses:
`ruff check --fix` retter lint-varsel, `ruff format` retter formateringen.
Kjør deretter sjekken på nytt for å bekrefte at alt er rettet.

### Eksisterende lint-konfigurasjon i målrepoet

Meld fra om hva som fantes av lint-konfigurasjon i målrepoet før den
overskrives — for eksempel en `[tool.ruff]`-blokk i `pyproject.toml`, en
eldre `ruff.toml` eller et annet lint-oppsett. Notér funnet der det passer
(commit-melding, issue eller notat).

Deretter overskrives den gamle konfigurasjonen med standarden som følger
testen: `ruff.toml` legges i rotkatalogen og erstatter konfigurasjonen som
var der fra før. Fjern eventuell eldre ruff-konfigurasjon den avløser (for
eksempel `[tool.ruff]`-blokka i `pyproject.toml`), slik at det ikke ligger
to konfigurasjoner som kjemper om hvilken som gjelder.

Regelsettet i `ruff.toml` er satt så komplett som praktisk mulig. Hvor
strengt nivået skal være i et gitt repo er et valg som bør avklares med den
som eier kravet — løft slike valg til menneske i stedet for å avgjøre dem
stille.

## Design conventions

Carried over from `utilities-perl/AGENTS.md`:

- **Fail hard.** Raise with context on unexpected input rather than silently
  continuing. Perl `die` -> Python `raise`; the Perl yada (`...`) operator ->
  `raise NotImplementedError`.
- POD documentation -> module/function docstrings.
