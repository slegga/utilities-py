# Arkitekturnotat: `scripts/sjekk-lint-tester.py`

Kortversjon: skriptet sjekker at linting er på plass i alle repoer under
`~/meta-privat` (ett nivå av underkataloger, ingen repo-liste) og endrer
aldri noe selv — det skriver ut fiks-kommandoer. Full dokumentasjon står i
skriptets docstring (`scripts/sjekk-lint-tester.py`) og i README.

- Python: linting skjer via delt git pre-commit-hook (`hooks/pre-commit`,
  referanse fra sak #2), ikke i `pytest`. Hooken skal være aktivert, kjøre
  `ruff` og være referansefilen kopiert uendret.
- Rust: lint-testen `tests/lint.rs` (referanse fra personlig-py sak #8) skal
  finnes, kjøres av `cargo test` og være kopiert uendret.
- Standard lint-konfigurasjon: ruff default uten egen konfigurasjon, med
  E501 ignorert (håndheves uansett ikke av default-regelsettet).
- Exit-koder: `0` alt OK, `1` minst ett avvik/mangler, `2` sjekkene kunne ikke
  fullføres. Reelle avvik (1) vinner over 2. `--json` for automatiserte
  kontroller.

Menneskevedtak og begrunnelser: sak #7 og #11 (inkludert «Ignore E501 skal
videreføres overalt», «trenger ikke repo-liste», vedlikeholdsansvar agent).
Skriptet tas ikke i bruk i automatiserte kontroller før mennesket eksplisitt
godkjenner det (sak #11 punkt 5).
