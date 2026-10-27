# Lint: kompleksitet og regelsett (historikk)

Status: **avgjort av eieren i sak #7** — ruff kjører med default-regelsett
uten egen konfigurasjon, via `hooks/pre-commit`. C901/PLR0912/PLR0915 er ikke
en del av standardregelsettet, så terskelvalget er uaktuelt med mindre
regelsettet utvides.

Prinsipper som fortsatt gjelder:

- Døde `# noqa`-er fjernes; begrunnelsen beholdes som kommentar. Unntak som
  håndheves av standardregelsettet beholdes med begrunnelse på samme linje —
  i dag: `# noqa: TRY004` (to steder) og `# noqa: BLE001`.
- Refaktoreringen fra sak #5 (hjelpefunksjoner trukket ut av `ask`,
  `csv_lastpass.read`, `exporters.export`, `cmd_file_forwarder` m.fl.) står.
  Der senere forenklinger har slått sammen duplikater igjen, er hjelperne
  beholdt som fasit — de er låst av enhetstester.

## Åpne forbedringsvalg (krever eierbeslutning, endrer oppførsel)

4. `winord.py`: migrer til argv-lister (fanger manglende `wmctrl` med tydelig
   feilmelding)? I dag beholdes `shell=True` for uendret oppførsel.
5. `alert.py`: avvise URL-skjema utenfor http/https? I dag lar `urllib`
   håndtere skjemaene som før. Krever tester — alert har ingen i dag.
6. Løst: `pyproject.toml` har nå kun `[project.optional-dependencies]`
   (`pip install -e ".[dev]"`, se README). `[dependency-groups]` er fjernet.
