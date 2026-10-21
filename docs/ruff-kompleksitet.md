# Pro/contra: kompleksitetsnivå for C901, PLR0912 og PLR0915

tags: `architecture`, `lint`, `decision-support`

Status: **åpen beslutning — venter på eieren av kravet** (jfr. «Ruff-nivå» i
`tests/test_lint.py` og kommentaren om PLR2004 i `ruff.toml`; slike nivåvalg
skal ikke avgjøres stille i leveransen).

## Status etter sak #5 (fakta, ingen beslutning)

Arbeidspakken i sak #5 lød «Rydd opp i eksisterende lint- og formatavvik i
utilities-py slik at hele testsettet går grønt, uten å endre funksjonalitet».
Avvikene nedenfor er derfor lukket i koden ved å trekke ut hjelpefunksjoner
(alternativ A i listen under) — ikke ved å endre terskler eller regelsett i
`ruff.toml`, som står uendret. `test_ruff_check` går nå grønt med
`uv run --with pytest pytest`.

Nivåvalget er dermed **ikke** tatt: regelbredde og terskler i `ruff.toml`
(evt. pedantic/preview, og PLR2004) er fortsatt eierens valg, jfr. sak #7.
Hvis eieren heller vil ha alternativ B eller C, kan refaktoreringen reverseres
— tabellen under viser avvikene slik de var før oppryddingen, som grunnlag for
veiingen «hvor mange avvik regelsettet skaper i eksisterende kode».

## Code review av sak #5 — funn og håndtering (fakta, ingen beslutning)

Code review avdekket at flere av PTH-/S-oppryddingene endret oppførsel i
grensetilfeller, i strid med arbeidspakkens krav «uten å endre
funksjonalitet». Alle er derfor gjenopprettet til opprinnelig oppførsel og
låst med enhetstester:

| Funn | Håndtering | Låst av |
| ---- | ---------- | ------- |
| `exporters.py` — `Path(...).name` er ikke ekvivalent med `os.path.basename` når stien ender på `/` | `os.path.basename` gjenopprettet med `# noqa: PTH119` | `test_lastpass_entry_jobb_mappe_med_sluttende_skrastrek` |
| `exporters.py` — `str(path.parent / new)` erstattet hele stien for absolutte navn i edit-file-2 | Gammel sammenføyning `(dir_ + "/" if dir_ else "") + new` med `os.path.dirname` (`# noqa: PTH120`) | `test_keep_edit_file_2_absolutt_navn_blir_under_mappen` |
| `winord.py` — argv-lister kastet `FileNotFoundError` når `wmctrl` mangler (ga før stille exit 127), og utskriftsformatet endret seg | `shell=True` med strengkommando gjenopprettet med `# noqa: S602` | se åpent spørsmål 4 |
| `importers.py` — sitering av tabellnavn brøt skjemakvalifiserte navn som `main.t` | Siteringen beholdt, men per prikk-separert identifikator (`_quote_ident`) slik at `main.t` virker; `# noqa: S608` beholdt | `test_sqlitetable_skjemakvalifisert_tabellnavn`, `test_sqlitetable_tabellnavn_med_unicode_og_sitatstegn` |
| `alert.py` — `ValueError` for URL-skjema utenfor http/https endret oppførsel for `url=` med f.eks. `file://` | Hardeningen fjernet; `# noqa: S310` dekker regelen | se åpent spørsmål 5 |
| `pyproject.toml` — `[project.optional-dependencies]` var byttet til `[dependency-groups]`, som brøt `pip install -e ".[dev]"` (dokumentert i README) | Begge seksjonene står nå med samme `dev`-liste: `dependency-groups` gjør at `uv run` installerer ruff for `uv run --with pytest pytest`, `optional-dependencies` holder `pip install -e ".[dev]"` og `uv sync --extra dev` i live | se åpent spørsmål 6 |

### Åpne forbedringsvalg som er løftet til eieren

Disse er ikke avgjørt av agenten; dagens kode følger «uten å endre
funksjonalitet», og alternativene krever eierbeslutning:

4.  **`winord.py`**: migrere til argv-lister? Da må manglende `wmctrl` fanges
    med tydelig feilmelding (i stedet for stille exit 127) og winord må få
    tester; utskriftsformatet for `print` vil også endre sitater rundt
    vindus-ID-ene. Alternativet er sikrere mot shell-sitering, men endrer
    oppførsel. Dagens løsning beholder `shell=True` med `# noqa: S602`.
5.  **`alert.py`**: ta inn S310-hardingen (avvis URL-skjema utenfor
    http/https)? I så fall bør endringen begrunnes og testes — alert har
    ingen tester i dag. Dagens løsning lar `urllib` håndtere skjemaene som
    før.
6.  **`pyproject.toml`**: forenkle til kun én av `[dependency-groups]` og
    `[project.optional-dependencies]`? Førstnevnte sikrer at `uv run`
    installerer dev-gruppen (nødvendig for kravet om at
    `uv run --with pytest pytest` kjører lint-testen), sistnevnte holder
    README-dokumentert `pip install -e ".[dev]"` i live. Å beholde begge
    koster én duplisert liste.

## Problembeskrivelse

`ruff.toml` følger ruff sine standardterskler for kompleksitet:

| Regel     | Terskel            | Avvik i produksjonskoden (før sak #5) |
| --------- | ------------------ | ------------------------------------- |
| C901      | kompleksitet > 10  | 7 funksjoner                          |
| PLR0912   | grener > 12        | 4 funksjoner                          |
| PLR0915   | setninger > 50     | 2 funksjoner                          |

Funksjonene som brøt tersklene, og som ble trukket ut i hjelpefunksjoner i
sak #5 (alle med uendret oppførsel — testsettet låser hjelpefunksjonene i
`ask`, `PassCodeExporter` og `cmd_file_forwarder` med enhetstester, og dekker
i tillegg grensetilfellene som ble avdekket i code review, se «Code review av
sak #5» over):

| Funksjon                                | C901 | PLR0912 | PLR0915 |
| --------------------------------------- | ---- | ------- | ------- |
| `utilities_perl/ask.py` — `ask`         | 20   | 23      | 57      |
| `utilities_perl/cli.py` — `cmd_file_forwarder` | 11 | –     | –       |
| `utilities_perl/csv_lastpass.py` — `read` | 30  | 34      | 103     |
| `utilities_perl/email_to_hash.py` — `parameterify` | 14 | 15 | –   |
| `utilities_perl/email_to_hash.py` — `_decode_content` | 12 | – | – |
| `utilities_perl/transform/exporters.py` — `export` | 21 | 20 | – |
| `rpg_common/template.py` — `ctable`     | ja (var dempet med `# noqa: C901`) | – | – |

I tillegg har `rpg_common/template.py` `# noqa: ARG001` på `clist` sin
`category` og `gterning` sin `number` (beholdte parametere som speiler
Perl-originalenes signaturer). Disse er nå begrunnet i docstringene
(«brukes ikke direkte, men beholdt for API-kompatibilitet»), og `clist` sin
docstring er rettet (den hevdet feilaktig at `category` brukes til
feilmeldinger).

Koden er Python-porter av Perl-moduler der lange prosedyriske funksjoner
speiler originalstrukturen bevisst, for å lette sammenligning og senere porter.
Uttrekkingen av hjelpefunksjoner i sak #5 avviker fra den strukturen, og det
er ett av momentene eieren bør vurdere når alternativ A skal bekreftes eller
avvises.

## Alternativer

### A. Refaktorér funksjonene til mindre hjelpefunksjoner

*   **For:** Beholder dagens strenge terskler som varige varsler for ny kode;
    lesbarhet og testbarhet blir bedre; ingen regelendring som må forsvares.
*   **Mot:** Stor og risikofylt diff, spesielt `read` (103 setninger) der
    CSV-logikken er intrikat; avviker fra Perl-strukturen og gjør
    side-ved-side-sammenligning med originalen vanskeligere; krever omfattende
    regresjonstesting.

### B. Hev tersklene i `ruff.toml` (f.eks. `max-complexity`, `max-branches`, `max-statements`)

*   **For:** Liten og forutsigbar diff; reglene forblir på som varsler på et
    realistisk nivå for prosedyriske porter; ny kode fanges fortsatt opp når
    den blir verre enn dagens funksjoner.
*   **Mot:** Svekker oppdagelsen av kompleksitet i ny kode; terskelverdiene
    blir skjønnsmessige og må begrunnes; kan skjule reell rot.

### C. Per-fil-ignores eller eksplisitte `noqa` med begrunnelse per funksjon

*   **For:** Global strenghet beholdes uendret; hvert avvik dokumenteres der
    det oppstår; lite endring i produksjonskoden.
*   **Mot:** Repeterer mønsteret med «stille noqa-er» med mindre hver begrunnelse
    er grundig; støy i kildekoden; nye funksjoner får samme avvik uten at
    terskelen i seg selv endres.

## Åpent spørsmål til beslutningstaker

1.  Hvilket alternativ skal brukes — A (refaktor), B (hev tersklene) eller
    C (per-fil-ignores/noqa)? Sak #5 gjennomførte A som del av oppryddingen
    (arbeidspakkens «rydde opp i avvik … uten å endre funksjonalitet»).
    Eieren bør bekrefte at A skal stå, eller velge B/C — i så fall reverseres
    refaktoreringen og `ruff.toml` justeres.
2.  Hvis B: hvilke terskelverdier, og skal de samme nivåene gjelde C901,
    PLR0912 og PLR0915 likt?
3.  Uansett alternativ: `ctable` i `rpg_common/template.py` skal behandles
    likt med de øvrige seks funksjonene (den stille `# noqa: C901` fjernes
    eller begrunnes), og `# noqa: ARG001` på `clist`/`gterning` skal begrunnes
    eller erstattes med en annen konsekvent løsning. Sak #5 fjernet
    `# noqa: C901` ved å trekke ut hjelpefunksjoner i `ctable`, og begrunnet
    `# noqa: ARG001` i docstringene. Eieren kan fortsatt velge en annen
    konsekvent løsning.

## Etter beslutningen

Valgt løsning brukes konsekvent i hele repoet, `test_ruff_check` skal gå grønt
med `uv run --with pytest pytest` (oppfylt etter sak #5), og beslutningen
dokumenteres (ikke i ADR fra agentens side — eieren skriver eventuelt selv).
