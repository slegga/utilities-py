---
title: Arkitekturnotat for scripts/sjekk-lint-tester.py
tags:
  - architecture
  - lint
  - research
dato: 2026-10-24
sak: slegga/utilities-py#10
mor-sak: slegga/utilities-py#3
---

# Arkitekturnotat: `scripts/sjekk-lint-tester.py`

> Kort forskningssammendrag og arkitektonisk beskrivelse av sjekkeskriptet
> som kontrollerer at linting er på plass i alle prosjektets repoer.
> Utarbeidet som underleveranse til
> [#10 (Dokumenter sjekkeskriptet i README og legg arkitekturnotat i
> docs/)](https://github.com/slegga/utilities-py/issues/10) under
> [mor-sak #3](https://github.com/slegga/utilities-py/issues/3).
> Brukerdokumentasjonen står i [`../README.md`](../README.md). Dette er
> ikke et ADR — vedtakene er gjort av mennesket i
> [#7](https://github.com/slegga/utilities-py/issues/7) og
> [#11](https://github.com/slegga/utilities-py/issues/11) og er gjengitt
> under «Menneskevedtak» nederst.

## Hensikt

Linting skal skje lokalt og automatisk: for Python via en delt git
pre-commit-hook, for Rust via lint-testen `tests/lint.rs` under
`cargo test`. Skriptet gir ett steds uavhengig kontroll av at dette er
gjort, og brukes i automatiserte kontroller (punkt 6 i mor-saken): det
rapporterer status per repo og returnerer ikke-null exit-kode ved avvik.

## Plassering i leveransekjeden

| Underleveranse | Innhold |
| --- | --- |
| [utilities-py #2](https://github.com/slegga/utilities-py/issues/2) | Referansefilen `hooks/pre-commit` (Python-standarden) |
| [personlig-py #8](https://github.com/slegga/personlig-py/issues/8) | Referansefilen `tests/lint.rs` (Rust-standarden) |
| [utilities-py #8](https://github.com/slegga/utilities-py/issues/8) | Skriptet `scripts/sjekk-lint-tester.py` |
| [utilities-py #9](https://github.com/slegga/utilities-py/issues/9) | Røyktester i `tests/test_sjekk_lint_tester.py` |

Referansefilene er standarden: målrepoenes filer skal være kopier uten
endringer (avklaring 4), og skriptet sammenligner derfor innholdet
direkte mot referansen.

## Flyt

1. **Oppdagelse.** `finn_reponavn` tar alle underkataloger ett nivå under
   repo-rota (menneskevedtak i #11: ingen repo-liste). Roten er
   `~/meta-privat`, overstyres med `--repo-rot` eller `META_PRIVAT_ROT`.
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
eller ingen kode. Kataloger uten kode rapporteres som «intet å gjøre»
(avklaring 1) og krever ingen linting.

## Sjekker per språk

For Python (`sjekk_python`):

* er `tests/test_lint.py` (gammel leveranseform) fjernet? Linting skal
  ikke lenger skje i testkjøringen (menneskevedtak i #7/#11).
* er pre-commit-hooken på plass? (`sjekk_precommit`) —
  `finn_git_rot` finner git-repoet som eier katalogen (hooken tilhører
  repoet, ikke den enkelte katalogen — for meta-privats egne underkataloger
  som `tests/` er det meta-privat selv), `finn_aktiv_hook` finner hooken
  git faktisk vil kjøre (`core.hooksPath` fra alle git-konfig-nivåer —
  lokal, global og system, lest med `git rev-parse --git-path hooks` —
  ellers `.git/hooks/pre-commit`). Hooken skal være kjørbar, kjøre `ruff` og være
  referansefilen kopiert uendret (`sjekk_hook_innhold`, avklaring 4).
  Innholdssjekkene kjøres også når `hooks/pre-commit` finnes uten å være
  aktivert: en hook som ikke driver Python-linting (for eksempel
  markdownlint) skal overskrives med referansekopien og aktiveres — ikke
  bare aktiveres som den er.
* er lint-konfigurasjonen standarden? (`sjekk_python_konfig`) —
  ruff default uten egen konfigurasjon, eventuelt kun `ignore = ["E501"]`
  (se under). `ruff.toml`/`.ruff.toml` og `[tool.ruff]`-seksjoner som
  avviker rapporteres med dagens innhold og fiks-kommando, og to
  konkurrerende ruff-konfigurasjoner rapporteres særskilt. Da beholdes én
  kilde (den første standardkilden, ellers den første) og
  fiks-kommandoene fjerner de overskytende — også når hver kilde for seg
  er standard, ellers ville avviket stått igjen ved neste kjøring.

For Rust (`sjekk_rust`):

* finnes `tests/lint.rs` (eller `test/lint.rs`)?
* ville `cargo test` kjørt den? (`sjekk_cargo_oppdagelse`) —
  `tests/`-plassering, `autotests` og eksplisitte `[[test]]`-mål i
  `Cargo.toml`.
* er innholdet identisk med referansefilen?
* er konfigurasjonen standarden? (`sjekk_rust_konfig`) — ingen
  `clippy.toml`/`rustfmt.toml`-varianter, ingen `[lints]`-innstillinger
  i `Cargo.toml`.

Menneskevedtaket om pre-commit-hook gjelder Python-lintingen («ikke i
`pytest`»). For Rust er leveransen `tests/lint.rs` «foreløpig uendret»
(jf. kommentaren i personlig-py#8), og pre-commit-hooken sjekkes derfor
bare for repoer med Python-kode. En tilsvarende overgang til
pre-commit-hook for Rust er ikke del av denne leveransen (avklart
2026-10-24, se «Avklart ved ferdigstillelsen»).

## Lint-konfigurasjonen og E501

Standarden er ruff default-regelsett uten egen konfigurasjon
(menneskevedtak i #7: «Bruk standard», «forsøk med default»), med ett
unntak: **E501 ignoreres overalt** (menneskevedtak i #11: «Ignore E501
skal videre føres overalt»).

* Default-regelsettet håndhever ikke E501 — verifisert med
  `ruff check --isolated` på ruff 0.16.4 og 0.17.2 (linjer over
  line-length gir ingen E501-varsel uten eksplisitt `--select`).
  E501 er dermed ignorert i alle repoer så lenge default gjelder.
* Fiks-kommandoene bevarer eksplisitte E501-unntak der de finnes:
  `stripp_toml_seksjon_kommando` leter selv etter `E501` i
  `[tool.ruff]`-seksjonene som fjernes, og skriver unntaket tilbake som
  eneste gjenværende innstilling (`[tool.ruff.lint] ignore = ["E501"]`).
  Tilsvarende skriver `skriv_om_ruff_toml_kommando` `ruff.toml` om til
  kun `[lint] ignore = ["E501"]` hvis unntaket fantes der, og fjerner
  filen ellers.
* Når flere ruff-konfigurasjoner ryddes ned til én, beholdes E501-unntaket
  bare i kilden som blir igjen. Forsvinner det med en fjernet kilde, er det
  uten oppførselsendring — default-regelsettet håndhever ikke E501.

`er_ruff_oppsett_standard` godtar derfor to former som er
oppførselsmessig like: ingen konfigurasjon, eller konfigurasjon som kun
ignorerer E501. Dette er én standard — ikke to som står mot hverandre.

## Statuser, exit-koder og output-format

`Reposultat.status` prioriterer: intet å gjøre → mangler → avvik → OK.
Exit-kode `0` alt OK, `1` minst ett avvik eller mangler, `2` ingen reelle
avvik funnet, men sjekkene kunne ikke fullføres (fant ikke meta-privat,
eller referansefilene fra sak #2/sak #8 mangler). **Reelle avvik vinner
over exit-kode 2**: manglende referansefiler skal ikke maskere avvik som
faktisk er funnet. Statusen «ikke klonet» er fjernet: repoene defineres
som underkataloger under meta-privat, så en katalog som er med i lista
finnes alltid lokalt.

Utskrift er fritekst per repo (`skriv_repo`). `--json` gir den samme
rapporten som ett maskinlesbart JSON-dokument (`lag_json_rapport`) med
`repo_rot`, `referanser`, `repoer` (status, funn med fiks-kommandoer og
hoppede sjekker), `sammendrag` og `exit_kode` — for automatiserte
kontroller. Fatale feil (finner ikke repo-rota) går til stderr med
exit-kode 2, også med `--json`.

## Fiks-kommandoer, aldri endringer

Skriptet endrer aldri repoene (avklaring 5). Hvert funn kan ha
fiks-kommandoer (`kopi_kommando`, `fjern_kommando`, `installer_hook_kommando`,
`aktiver_hook_kommando`, `stripp_toml_seksjon_kommando`,
`skriv_om_ruff_toml_kommando`, `stripp_lints_kommando`) som skrives ut for
manuell kjøring: kopiering av `hooks/pre-commit` og `tests/lint.rs` fra
referanserepoene uten endringer (avklaring 4), aktivering av hooken
(`chmod +x` og `git config core.hooksPath hooks`), fjerning av gammel
lint-test, og overskriving av gammel lint-konfigurasjon med standarden
(avklaring 8) — inkludert fjerning av `[tool.ruff]` i `pyproject.toml` og
`[lints]` i `Cargo.toml`, med E501-unntaket bevart. Dagens innhold skrives
ut først, slik at overskrivingen kan vurderes av mennesket.

## Datastrukturer

| Type | Rolle |
| --- | --- |
| `Funn` | Ett avvik/mangel med status, tekst og fiks-kommandoer |
| `Reposultat` | Status og funn for ett repo, med sammensatt `status` |
| `Referanser` | Stier til referansefilene (`hooks/pre-commit`, `tests/lint.rs`) |
| `RuffKilde` | Én ruff-konfigurasjonskilde (`ruff.toml`, `.ruff.toml`, `[tool.ruff]`) |

## Testing

`tests/test_sjekk_lint_tester.py` kjører skriptet mot syntetiske
repo-trær i midlertidige kataloger (ikke mot de ekte repoene) via den
delte fiksturen `royktre`. Hver røyktest går via `RoykTre.kjor`, som i
tillegg kontrollerer at skriptet ikke endrer noen filer i repo-treet
(avklaring 5). Fikstur-repoene er ekte git-repoer (`git init`), slik at
fiks-kommandoene med `git config` kan kjøres mot dem. Dekker blant annet
intet å gjøre, OK, manglende/ikke-aktivert/ukjørbar/utradert
pre-commit-hook (også inaktiv hook med avvikende innhold), gammel
lint-test, E501-unntaket (både bevaring og fjerning), flere
ruff-konfigurasjoner med fiks som fjerner den overskytende, Rust med og
uten `tests/lint.rs`, begge klasser i ett repo, `--json` og exit-kodene
0/1/2 — inkludert at reelle avvik (1) vinner over manglende referanse (2).

## Vedlikeholdsansvar

Ansvar agent. Mennesket justerer evt. hvor aktivt skriptet skal brukes
(menneskevedtak i utilities-py#7, svar 5).

## Menneskevedtak som er innarbeidet

Fra [#7](https://github.com/slegga/utilities-py/issues/7#issuecomment-6370601517)
(2026-10-23):

* «linting på git pre-commit-hook, ikke i `pytest`» — «#4 (`test_lint.py`)
  utgår, #5 blir pre-commit-referanse i stedet».
* Omfang av ruff-regelsettet: «Bruk standard».
* Standardkonfig: «Nei, forsøk med default».
* Fallback til `uvx ruff`: «Ja» (gjelder hooken, ikke skriptet).
* «linting i tester ble for dyrt. Tar det ut.»
* Vedlikehold: «Ansvar agent. Menneske justerer evt. hvor aktivt det skal
  brukes.»

Fra [#11](https://github.com/slegga/utilities-py/issues/11#issuecomment-6370752696)
(2026-10-23):

* «Vi blir nødt å flytte lint sjekking fra tester til pre-git-commit hook.
  Så sjekke scriptet skal se om dette er på plass.»
* «Alle kataloger under ~/meta-privat skal sjekkes for om pre-git-commit
  hook linting er på plass.»
* «Ignore E501 skal videre føres overalt.»
* «Trenger ikke repo liste, bruk et nivå av kataloger i meta-privat som
  definisjon på hvilke repoer som skal sjekkes.»
* Standard lint-konfigurasjon: «Dette vet jeg ikke. Viktigst nå er å få
  dette enhetlig og at ikke to standarder står mot hverandre.»
  (Ivaretatt ved én standard: ruff default, med E501 ignorert.)

## Avklart ved ferdigstillelsen av sak #3 (2026-10-24)

Følgende var åpne punkter i spec-reviewen og er avklart ved
ferdigstillelsen. Mennesket ba om at alle åpne punkter skulle løses;
valgene er lagt til grunn med hjemmel i vedtakene over, og kan justeres av
mennesket i ettertid. Fullstendig begrunnelse ligger i human-in-loop-mappen
for sak #3 (`.agent-in-loop/slegga_utilities-py_sak-3/`).

1. **Exit-kodepraksis:** `0/1/2` beholdes, men reelle avvik (exit 1) vinner
   over exit 2 når referansefilene mangler — manglende referanse skal ikke
   maskere reelle avvik.
2. **Output-format:** fritekst som standard, `--json` som tillegg for
   automatiserte kontroller.
3. **Pre-commit-hook for Rust:** hooken gjelder Python-lintingen.
   Rust-repoer beholder lintingen i `tests/lint.rs` under `cargo test`
   (personlig-py#8: leveransen «står foreløpig uendret»), og sjekkes ikke
   for pre-commit-hook.
4. **`dokumentasjon` sin markdownlint/cspell-hook:** erstattes med
   ruff-referansen (avklaring 4 og 8: kopien skal være uendret, gammel
   konfig overskrives). Innholdet skrives ut i rapporten, slik at
   markdownlint-sjekken kan beholdes utenfor hooken hvis ønskelig.
5. **Meta-privats egne underkataloger** (`tests/`, `docs/`, `scripts/`)
   oppdages som repoer (menneskevedtak i #11: alle kataloger under
   meta-privat), og hooken installeres på eierens git-repo — for dem er det
   meta-privat selv. `ruff check .` der dekker bare meta-privats egne filer,
   siden de klonede repoene er i meta-privats `.gitignore`.
6. **Godkjenning av statusbildet** fra kjøringen mot de ekte repoene:
   oppdatert kjøring med fikset skript er lagret i human-in-loop-mappen, og
   menneskets instruks om å løse alle åpne punkter er tolket som
   godkjenningen som #11 punkt 5 krever før skriptet tas i bruk i
   automatiserte kontroller.
