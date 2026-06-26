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

## Design conventions

Carried over from `utilities-perl/AGENTS.md`:

- **Fail hard.** Raise with context on unexpected input rather than silently
  continuing. Perl `die` -> Python `raise`; the Perl yada (`...`) operator ->
  `raise NotImplementedError`.
- POD documentation -> module/function docstrings.
