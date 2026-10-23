---
title: Arkitekturnotat for scripts/sjekk-lint-tester.py
tags:
  - architecture
  - lint
  - research
dato: 2026-10-23
sak: slegga/utilities-py#10
mor-sak: slegga/utilities-py#3
---

# Arkitekturnotat: `scripts/sjekk-lint-tester.py`

> Kort forskningssammendrag og arkitektonisk beskrivelse av sjekkeskriptet
> som kontrollerer lint-testene i alle prosjektets repoer. Utarbeidet som
> underleveranse til
> [#10 (Dokumenter sjekkeskriptet i README og legg arkitekturnotat i
> docs/)](https://github.com/slegga/utilities-py/issues/10) under
> [mor-sak #3](https://github.com/slegga/utilities-py/issues/3).
> Brukerdokumentasjonen står i [`../README.md`](../README.md). Dette er
> ikke et ADR — ingen beslutninger tas her, se «Åpne spørsmål» nederst.

## Hensikt

Lint-testene (`tests/test_lint.py` for Python, `tests/lint.rs` for Rust)
er delbare filer som kopieres uendret mellom repoer. Skriptet gir ett
steds uavhengig kontroll av at dette er gjort, og brukes i automatiserte
kontroller (punkt 6 i mor-saken): det rapporterer status per repo og
returnerer ikke-null exit-kode ved avvik.

## Plassering i leveransekjeden

| Underleveranse | Innhold |
| --- | --- |
| [utilities-py #2](https://github.com/slegga/utilities-py/issues/2) | Referansefilene `tests/test_lint.py` og `ruff.toml` (Python-standarden) |
| [personlig-py #8](https://github.com/slegga/personlig-py/issues/8) | Referansefilen `tests/lint.rs` (Rust-standarden) |
| [utilities-py #8](https://github.com/slegga/utilities-py/issues/8) | Skriptet `scripts/sjekk-lint-tester.py` |
| [utilities-py #9](https://github.com/slegga/utilities-py/issues/9) | Røyktester i `tests/test_sjekk_lint_tester.py` |

Referansefilene er standarden: målrepoenes filer skal være kopier uten
endringer (avklaring 4), og skriptet sammenligner derfor innholdet
direkte mot referansen.

## Flyt

1. **Plassering.** `finn_plassering` bestemmer repo-rot og repoliste:
   `--repo-rot`/`--repo-liste` (fiksturer i tester), ellers `config.yaml`
   i meta-privat der `repogruppe` peker på lista (f.eks. `repos-all.txt`)
   og `repos_dir` sier hvor repoene ligger. Meta-privat finnes via
   `--meta-rot`, `META_PRIVAT_ROT` eller søk oppover fra skriptet og
   arbeidskatalogen.
2. **Referanser.** `finn_referanser` leter etter referansefilene under
   repo-rota. Mangler de, skriver skriptet tydelig varsel, hopper over
   sjekkene som trenger dem og avslutter med exit-kode 2.
3. **Per repo** (`sjekk_repo`): klassifisering, deretter sjekker for
   Python og/eller Rust, og til slutt utskrift (`skriv_repo`) med funn og
   fiks-kommandoer.

## Klassifisering

`klassifiser` leter etter `*.py`/`*.rs` (med kataloger som `.venv`,
`target`, `node_modules` hoppet over) og teller også `pyproject.toml`
som Python og `Cargo.toml` som Rust. Resultatet er Python, Rust, begge
eller ingen kode. Repoer uten kode rapporteres som «intet å gjøre»
(avklaring 1) og krever ingen lint-test.

## Sjekker per språk

For Python (`sjekk_python`):

* finnes `tests/test_lint.py` (eller `test/test_lint.py`)?
* ville pytest samlet den inn? `les_pytest_oppsett` leser
  `testpaths`/`python_files` fra `pytest.ini`, `pyproject.toml`,
  `tox.ini` eller `setup.cfg`, og `sjekk_pytest_oppdagelse` vurderer
  mot filplassering og filnavn-mønster.
* er innholdet identisk med referansefilen? (`sjekk_testinnhold`)
* er lint-konfigurasjonen standarden? (`sjekk_python_konfig`) —
  `ruff.toml` lik referansen, ingen overskrivende `.ruff.toml`, ingen
  `[tool.ruff]`-seksjoner i `pyproject.toml`.

For Rust (`sjekk_rust`):

* finnes `tests/lint.rs` (eller `test/lint.rs`)?
* ville `cargo test` kjørt den? (`sjekk_cargo_oppdagelse`) —
  `tests/`-plassering, `autotests` og eksplisitte `[[test]]`-mål i
  `Cargo.toml`.
* er innholdet identisk med referansefilen?
* er konfigurasjonen standarden? (`sjekk_rust_konfig`) — ingen
  `clippy.toml`/`rustfmt.toml`-varianter, ingen `[lints]`-innstillinger
  i `Cargo.toml`.

## Statuser og exit-koder

`Reposultat.status` prioriterer: ikke klonet → intet å gjøre → mangler →
avvik → OK. Exit-kode `0` alt OK, `1` minst ett avvik eller mangler, `2`
sjekkene kunne ikke fullføres. Repoer som ikke er klonet lokalt
(«ikke klonet») telles i sammendraget, men påvirker ikke exit-koden, slik
at uregistrerte repoer i `repos-all.txt` ikke bryter automatiserte
kontroller.

## Fiks-kommandoer, aldri endringer

Skriptet endrer aldri repoene (avklaring 5). Hvert funn kan ha
fiks-kommandoer (`kopi_kommando`, `fjern_kommando`,
`stripp_toml_seksjon_kommando`, `stripp_lints_kommando`) som skrives ut
for manuell kjøring: kopiering av testfilene fra referanserepoene uten
endringer (avklaring 4), og overskriving av gammel lint-konfigurasjon med
standarden (avklaring 8) — inkludert fjerning av `[tool.ruff]` i
`pyproject.toml` og `[lints]` i `Cargo.toml`. Dagens innhold skrives ut
først, slik at overskrivingen kan vurderes av mennesket.

## Datastrukturer

| Type | Rolle |
| --- | --- |
| `Funn` | Ett avvik/mangel med status, tekst og fiks-kommandoer |
| `Reposultat` | Status og funn for ett repo, med sammensatt `status` |
| `Referanser` | Stier til referansefilene, med oversikt over manglende |
| `Plassering` | Repo-rot og eventuell repoliste |
| `PytestOppsett` | `testpaths`/`python_files` som styrer pytest-oppdagelsen |

## Testing

`tests/test_sjekk_lint_tester.py` kjører skriptet mot syntetiske
repo-trær i midlertidige kataloger (ikke mot de ekte repoene) via den
delte fiksturen `royktre`. Hver røyktest går via `RoykTre.kjor`, som
i tillegg kontrollerer at skriptet ikke endrer noen filer i repo-treet
(avklaring 5). Dekker blant annet intet å gjøre, OK, mangler, avvikende
`[tool.ruff]`, Rust med og uten `tests/lint.rs`, begge klasser i ett
repo og exit-kodene 0/1/2.

## Åpne spørsmål for mennesket

Verdiene nedenfor er implementert i skriptet i dag, men trenger
godkjennelse av menneske — de er ikke besluttet av agenten (jf.
gjennomgangen av sak #8):

1. **Exit-kode 2 når referansefilene mangler.** Saken sier «tåle at
   referansefilene ikke finnes ennå og gi tydelig melding» og «ikke-null
   ved avvik». Exit 2 overstyrer exit 1 ved reelle avvik og ville fått
   automatiserte kontroller til å feile i perioden før sak #2/#8 var på
   plass. Skal exit 2 beholdes slik den er i dag?
2. **Statusen «ikke klonet» som ikke påvirker exit-koden.** Saken lister
   bare OK, mangler, avvik og intet å gjøre. Skal statusen og
   oppførselen beholdes?
3. **`github-issue-pipeline` sin midlertidige `E501`-ignore** i
   `[tool.ruff]` er en bevisst utsettelse. Fiks-kommandoen overskriver
   den med standarden (avklaring 8) — skal den overskrives, eller
   flagges spesielt?
4. **Output-format for automatiserte kontroller** (punkt 6 i mor-saken).
   Dagens utskrift er fritekst per repo. Skal maskinlesbart format (for
   eksempel JSON) være tillegg eller alternativ?

Svarene hører hjemme i saken eller i human-in-loop-mappen — ikke i
dette dokumentet.
