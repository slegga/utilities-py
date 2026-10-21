# Pro/contra: kompleksitetsnivå for C901, PLR0912 og PLR0915

tags: `architecture`, `lint`, `decision-support`

Status: **åpen beslutning — venter på eieren av kravet** (jfr. «Ruff-nivå» i
`tests/test_lint.py` og kommentaren om PLR2004 i `ruff.toml`; slike nivåvalg
skal ikke avgjøres stille i leveransen).

## Problembeskrivelse

`ruff.toml` følger ruff sine standardterskler for kompleksitet:

| Regel     | Terskel            | Avvik i produksjonskoden                     |
| --------- | ------------------ | -------------------------------------------- |
| C901      | kompleksitet > 10  | 7 funksjoner                                 |
| PLR0912   | grener > 12        | 4 funksjoner                                 |
| PLR0915   | setninger > 50     | 2 funksjoner                                 |

Funksjonene som bryter tersklene:

| Funksjon                                | C901 | PLR0912 | PLR0915 |
| --------------------------------------- | ---- | ------- | ------- |
| `utilities_perl/ask.py` — `ask`         | 20   | 23      | 57      |
| `utilities_perl/cli.py` — `cmd_file_forwarder` | 11 | –     | –       |
| `utilities_perl/csv_lastpass.py` — `read` | 30  | 34      | 103     |
| `utilities_perl/email_to_hash.py` — `parameterify` | 14 | 15 | –   |
| `utilities_perl/email_to_hash.py` — `_decode_content` | 12 | – | – |
| `utilities_perl/transform/exporters.py` — `export` | 21 | 20 | – |
| `rpg_common/template.py` — `ctable`     | ja (dempet med `# noqa: C901`) | – | – |

I tillegg har `rpg_common/template.py` stille `# noqa: ARG001` på `clist` og
`gterning` (beholdte parametere som speiler Perl-originalenes signaturer).
Håndteringen er i dag blandet: én funksjon er dempet med stille `noqa`, seks
står uløst, og testen `test_ruff_check` er derfor rød.

Koden er Python-porter av Perl-moduler der lange prosedyriske funksjoner
speiler originalstrukturen bevisst, for å lette sammenligning og senere porter.

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
    C (per-fil-ignores/noqa)?
2.  Hvis B: hvilke terskelverdier, og skal de samme nivåene gjelde C901,
    PLR0912 og PLR0915 likt?
3.  Uansett alternativ: `ctable` i `rpg_common/template.py` skal behandles
    likt med de øvrige seks funksjonene (den stille `# noqa: C901` fjernes
    eller begrunnes), og `# noqa: ARG001` på `clist`/`gterning` skal begrunnes
    eller erstattes med en annen konsekvent løsning.

## Etter beslutningen

Valgt løsning brukes konsekvent i hele repoet, `test_ruff_check` skal gå grønt
med `uv run --with pytest pytest`, og beslutningen dokumenteres (ikke i ADR
fra agentens side — eieren skriver eventuelt selv).
