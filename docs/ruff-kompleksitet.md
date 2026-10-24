# Pro/contra: kompleksitetsnivå for C901, PLR0912 og PLR0915

tags: `architecture`, `lint`, `decision-support`

Status: **nivåvalget er avgjort av eieren i sak #7** — se «Status etter sak #7»
under. Pro/contra-oversikten er beholdt som historikk og grunnlag hvis
regelsettet senere utvides (slike nivåvalg skal ikke avgjøres stille i
leveransen).

## Status etter sak #5 (historikk — fakta, ingen beslutning)

Dette avsnittet beskriver tilstanden etter sak #5. `tests/test_lint.py` (med
`test_ruff_check`) og `ruff.toml` som omtales her, er siden fjernet i sak #7 —
se «Status etter sak #7» under.

Arbeidspakken i sak #5 lød «Rydd opp i eksisterende lint- og formatavvik i
utilities-py slik at hele testsettet går grønt, uten å endre funksjonalitet».
Avvikene nedenfor ble derfor lukket i koden ved å trekke ut hjelpefunksjoner
(alternativ A i listen under) — ikke ved å endre terskler eller regelsett i
`ruff.toml`, som da stod uendret. `test_ruff_check` gikk grønt med
`uv run --with pytest pytest`.

Nivåvalget ble dermed **ikke** tatt: regelbredde og terskler i `ruff.toml`
(evt. pedantic/preview, og PLR2004) var fortsatt eierens valg, jfr. sak #7.
Hvis eieren heller ville ha alternativ B eller C, kunne refaktoreringen
reverseres — tabellen under viser avvikene slik de var før oppryddingen, som
grunnlag for veiingen «hvor mange avvik regelsettet skaper i eksisterende
kode».

## Status etter sak #7 (fakta, ingen ny beslutning)

Eieren avklarte i sak #7 (menneskevedtak gjengitt i slegga/utilities-py#7,
kommentar 2026-10-23,
https://github.com/slegga/utilities-py/issues/7#issuecomment-6370601517 —
ikke i dette dokumentet): regelsettet skal være **standard** (ruff default,
uten egen konfigurasjon), og linting skal kjøres i **git pre-commit-hook**,
ikke i `pytest`. Konsekvenser for dette dokumentet:

- `tests/test_lint.py` og `ruff.toml` er fjernet; leveransen er i stedet
  `hooks/pre-commit` (se README).
- C901, PLR0912 og PLR0915 er ikke en del av standardregelsettet, så
  terskelvalget (alternativ A/B/C under) er ikke lenger aktuelt med dagens
  standard. Spørsmålet kan gjenoppstå hvis regelsettet utvides. Spørsmål 1–3
  nederst i dokumentet er dermed avgjort/utaktuelle.
- Vedlikeholdsansvar for lint-oppsettet er agentens; mennesket justerer hvor
  aktivt det skal brukes.
- `# noqa`-er for regler utenfor standardregelsettet (PTH-, S-, ARG- og
  PLC0415-regler) er fjernet som unødvendige; oppførsel de låste er uendret.
  Tre `# noqa` (TRY004 to steder, BLE001) er **ikke** døde og er beholdt med
  begrunnelse: TRY004 og BLE001 ligger i ruff sitt default-regelsett (utvidet
  fra 59 til 413 regler i ruff 0.16), og undertrykkelsene låser oppførsel som
  standardregelsettet ellers ville krevd endret (`raise ValueError` og bred
  `except Exception`). Prinsippet er ellers å fjerne døde `# noqa`-er, se
  README.
- Røyktester for hooken ligger i `tests/test_precommit_hook.py`: hooken
  kopieres uendret inn i et tmp-repo og kjøres mot villet lint- og formatfeil,
  med uvx-fallback og med manglende ruff/uvx, og mot en reell `git commit`.
  Testene erstatter den manuelle verifiseringen og dekker kravet om at filen
  virker uten repo-spesifikke tilpassinger.

## Skjult endring i lint-diffen: bugfix i `exporters.py` (fakta)

Endringssettet etter sak #7 blandet inn én funksjonsrettet bugfix i det som
ellers er rene lint- og formatendringer. Den er dokumentert her slik at den
ikke forblir skjult i formateringsdiffen:

`PassCodeExporter._passordfil_entry` i
`utilities_perl/transform/exporters.py` hadde
`re.sub(r"^https?+://", …)`, rettet til `re.sub(r"^https?://", …)`.

- `?+` (possessiv kvantor) er ugyldig i Python 3.9/3.10 og gir
  `re.error: multiple repeat`, så `_passordfil_entry` krasjet på repoets egen
  Python (`requires-python >= 3.9`, verifisert med 3.9.25). Buggen fantes fra
  før på `main`, men ble eksponert av testene sak #5 la til
  (`test_passordfil_entry_*`).
- Avstemt mot «uten å endre funksjonalitet»: på Python ≥ 3.11 matcher
  `https?://` og `https?+://` nøyaktig de samme strengene (possessiv kvantor
  endrer bare backtracking), så treffene er uendret. På 3.9/3.10 erstatter
  rettingen en krasj med tilsiktet oppførsel. Rettingen er altså en bugfix,
  ikke en funksjonsendring.
- Rettingen bør tas som egen `fix:`-commit, skilt fra formateringen, når
  endringssettet commites. `test_passordfil_entry_grunnleggende` og de øvrige
  `test_passordfil_entry_*`-testene låser strengene og dermed rettingen.

## Code review av sak #5 — funn og håndtering (fakta, ingen beslutning)

Code review avdekket at flere av PTH-/S-oppryddingene endret oppførsel i
grensetilfeller, i strid med arbeidspakkens krav «uten å endre
funksjonalitet». Alle er derfor gjenopprettet til opprinnelig oppførsel, og
er låst med enhetstester der slike finnes (se kolonnen «Låst av»):

| Funn | Håndtering | Låst av |
| ---- | ---------- | ------- |
| `exporters.py` — `Path(...).name` er ikke ekvivalent med `os.path.basename` når stien ender på `/` | `os.path.basename` gjenopprettet (opprinnelig med `# noqa: PTH119`) | `test_lastpass_entry_jobb_mappe_med_sluttende_skrastrek` |
| `exporters.py` — `str(path.parent / new)` erstattet hele stien for absolutte navn i edit-file-2 | Gammel sammenføyning `(dir_ + "/" if dir_ else "") + new` med `os.path.dirname` (opprinnelig med `# noqa: PTH120`) | `test_keep_edit_file_2_absolutt_navn_blir_under_mappen` |
| `winord.py` — argv-lister kastet `FileNotFoundError` når `wmctrl` mangler (ga før stille exit 127), og utskriftsformatet endret seg | `shell=True` med strengkommando gjenopprettet (opprinnelig med `# noqa: S602`) | se åpent spørsmål 4 |
| `importers.py` — sitering av tabellnavn (`_quote_ident`) brøt eksplisitt siterte/skilletegnsnavn som `main."t"` og tabell kalt `my.table` | Siteringen er **revertert til rå interpolering** (`select * from {args['table']}`) — opprinnelig oppførsel, i tråd med «uten å endre funksjonalitet». `# noqa: S608` er ikke nødvendig med standardregelsettet og er fjernet | `test_sqlitetable_skjemakvalifisert_tabellnavn`, `test_sqlitetable_tabellnavn_siteres_av_kalleren` |
| `alert.py` — `ValueError` for URL-skjema utenfor http/https endret oppførsel for `url=` med f.eks. `file://` | Hardeningen fjernet (opprinnelig dekket av `# noqa: S310`) | se åpent spørsmål 5 |
| `pyproject.toml` — `[project.optional-dependencies]` var byttet til `[dependency-groups]`, som brøt `pip install -e ".[dev]"` (dokumentert i README) | Begge seksjonene står nå med samme `dev`-liste: `dependency-groups` gjør at `uv run` installerer ruff for `uv run --with pytest pytest`, `optional-dependencies` holder `pip install -e ".[dev]"` og `uv sync --extra dev` i live | se åpent spørsmål 6 |

Merknad om `# noqa` i kolonnen over: PTH119, PTH120, S602, S608 og S310 var
med i håndteringen etter sak #5, men er fjernet i endringssettet etter sak #7
— reglene ligger utenfor standardregelsettet, så undertrykkelsene var døde
(se «Status etter sak #7»). Oppførselen de låste er uendret.

### Åpne forbedringsvalg som er løftet til eieren

Disse er ikke avgjørt av agenten; dagens kode følger «uten å endre
funksjonalitet», og alternativene krever eierbeslutning:

4.  **`winord.py`**: migrere til argv-lister? Da må manglende `wmctrl` fanges
    med tydelig feilmelding (i stedet for stille exit 127) og winord må få
    tester; utskriftsformatet for `print` vil også endre sitater rundt
    vindus-ID-ene. Alternativet er sikrere mot shell-sitering, men endrer
    oppførsel. Dagens løsning beholder `shell=True`.
5.  **`alert.py`**: ta inn S310-hardingen (avvis URL-skjema utenfor
    http/https)? I så fall bør endringen begrunnes og testes — alert har
    ingen tester i dag. Dagens løsning lar `urllib` håndtere skjemaene som
    før.
6.  **`pyproject.toml`**: forenkle til kun én av `[dependency-groups]` og
    `[project.optional-dependencies]`? Førstnevnte sikrer at `uv run`
    installerer dev-gruppen (ruff må være tilgjengelig for `uv run --with
    pytest pytest`, som hooken bruker), sistnevnte holder README-dokumentert
    `pip install -e ".[dev]"` i live. Å beholde begge koster én duplisert
    liste.

## Problembeskrivelse (historikk)

Dette avsnittet og alternativene under beskriver situasjonen da `ruff.toml`
fulgte ruff sine standardterskler for kompleksitet (filen er fjernet etter
sak #7):

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

## Spørsmål til beslutningstaker

**Spørsmål 1–3 er avgjort/utaktuelle etter sak #7:** vedtaket «Bruk standard»
og «forsøk med default» fjernet `ruff.toml`, og C901/PLR0912/PLR0915 er ikke
del av standardregelsettet. Spørsmålene er beholdt som historikk og kan
gjenopstå hvis regelsettet utvides. **Spørsmål 4–6 (under «Åpne
forbedringsvalg som er løftet til eieren») står fortsatt åpne.**

1.  Hvilket alternativ skal brukes — A (refaktor), B (hev tersklene) eller
    C (per-fil-ignores/noqa)? Sak #5 gjennomførte A som del av oppryddingen
    (arbeidspakkens «rydde opp i avvik … uten å endre funksjonalitet»).
    Eieren bør bekrefte at A skal stå, eller velge B/C — i så fall reverseres
    refaktoreringen og `ruff.toml` justeres. (Avgjort/utaktuelt etter sak #7:
    tersklene finnes ikke lenger; refaktoreringen fra sak #5 står.)
2.  Hvis B: hvilke terskelverdier, og skal de samme nivåene gjelde C901,
    PLR0912 og PLR0915 likt? (Avgjort/utaktuelt etter sak #7.)
3.  Uansett alternativ: `ctable` i `rpg_common/template.py` skal behandles
    likt med de øvrige seks funksjonene (den stille `# noqa: C901` fjernes
    eller begrunnes), og `# noqa: ARG001` på `clist`/`gterning` skal begrunnes
    eller erstattes med en annen konsekvent løsning. Sak #5 fjernet
    `# noqa: C901` ved å trekke ut hjelpefunksjoner i `ctable`, og begrunnet
    `# noqa: ARG001` i docstringene. Eieren kan fortsatt velge en annen
    konsekvent løsning. (Delvis avgjort etter sak #7: `# noqa: C901` er borte
    sammen med regelsettet, og begrunnelsene i docstringene står.)

## Etter beslutningen

Valgt løsning brukes konsekvent i hele repoet, `ruff check .` og
`ruff format --check .` skal gå grønt (i dag via pre-commit-hooken, se README;
tidligere via `test_ruff_check` i pytest), og beslutningen dokumenteres
(ikke i ADR fra agentens side — eieren skriver eventuelt selv).
