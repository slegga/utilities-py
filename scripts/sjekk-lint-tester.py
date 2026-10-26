#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["tomli>=2.0; python_version < '3.11'"]
# ///
"""Sjekk at linting er på plass i alle repoer under meta-privat.

Skriptet går gjennom alle kataloger ett nivå under meta-privat og
kontrollerer for hver av dem:

* klassifisering: Python, Rust, begge deler eller ingen kode, ut fra
  ``pyproject.toml`` og ``*.py``, ``Cargo.toml`` og ``*.rs``
* at linting skjer via git pre-commit-hook for Python (menneskevedtak i
  utilities-py#7 og #11) — hooken skal være aktivert, kjøre ``ruff`` og være
  referansefilen kopiert uendret (avklaring 4). Innholdet vurderes mot
  referansen også når hooken finnes uten å være aktivert.
* at den gamle lint-testen ``tests/test_lint.py`` er fjernet — linting skal
  ikke lenger skje i testkjøringen
* at lint-testen for Rust er på plass (``tests/lint.rs``, ``test/``
  aksepteres også) og kjøres av ``cargo test``
* at innholdet i ``tests/lint.rs`` er referansefilen kopiert uendret
  (avklaring 4)
* at lint-konfigurasjonen er standarden (ruff default uten egen
  konfigurasjon, rustfmt/clippy-oppsettet fra personlig-py sak #8)

Kataloger uten kode rapporteres som intet å gjøre (avklaring 1).

Skriptet endrer aldri repoene (avklaring 5). For hvert avvik skriver det ut
konkrete kommandoer som fikser avviket når du kjører dem selv — for eksempel
kopiering av pre-commit-hooken fra referanserepoet uten endringer, og
overskriving av gammel lint-konfigurasjon med standarden (avklaring 8).

## Slik finner skriptet repoene

Repoene er alle underkataloger ett nivå under meta-privat (menneskevedtak i
utilities-py#11: «Trenger ikke repo liste, bruk et nivå av kataloger i
meta-privat som definisjon»). Skjulte kataloger og byggeartefakter som
``__pycache__`` og ``.venv`` hoppes over. Roten er ``~/meta-privat``, og kan
overstyres med ``--repo-rot`` eller miljøvariabelen ``META_PRIVAT_ROT`` — for
eksempel mot et fikstur-tre i tester. Ingen repo-liste leses lenger. Også
meta-privats egne underkataloger (``tests/``, ``docs/``, ``scripts/``) tas med.
Pre-commit-hooken tilhører git-repoet som eier katalogen — for dem er det
meta-privat selv, og fiks-kommandoen installerer hooken der.

## Referansefiler

* Python: ``hooks/pre-commit`` i repoet ``utilities-py`` (sak #2)
* Rust: ``tests/lint.rs`` i repoet ``personlig-py`` (sak #8)

Hvis referansefilene ikke finnes ennå, sier skriptet tydelig ifra om det,
hopper over sjekkene som trenger dem og påvirker exit-koden (se under).

## Exit-kode

* ``0`` — alt OK (eventuelt intet å gjøre alle steder)
* ``1`` — minst ett avvik eller mangler. Reelle avvik vinner over exit-kode 2.
* ``2`` — ingen reelle avvik, men skriptet kunne ikke fullføre alle sjekkene
  (fant ikke meta-privat, eller referansefilene fra sak #2/sak #8 mangler)

Utskrift er fritekst per repo. ``--json`` gir den samme rapporten som ett
maskinlesbart JSON-dokument for automatiserte kontroller.

## Avklarte valg (menneskevedtak i utilities-py#7 og #11)

* Linting for Python skjer via en delt git pre-commit-hook, ikke som
  lint-test i pytest (utilities-py#7: «linting på git pre-commit-hook, ikke i
  ``pytest``», «#4 (``test_lint.py``) utgår, #5 blir pre-commit-referanse i
  stedet»; utilities-py#11: «Sjekke scriptet skal se om dette er på plass»).
* Repoene er ett nivå av kataloger under meta-privat, uten repo-liste
  (utilities-py#11: «Trenger ikke repo liste, bruk et nivå av kataloger»).
* Ruff kjører med default-regelsett uten egen konfigurasjon (utilities-py#7:
  «Bruk standard», «forsøk med default»). E501 ignoreres overalt
  (utilities-py#11: «Ignore E501 skal videre føres overalt»):
  default-regelsettet håndhever ikke E501, og fiks-kommandoene bevarer
  eksplisitte E501-unntak der de finnes.
* Vedlikeholdsansvar er agentens. Mennesket justerer evt. hvor aktivt
  skriptet skal brukes (utilities-py#7).

## Avklart ved ferdigstillelsen av sak #3 (2026-10-24)

Følgende var åpne punkter i spec-reviewen og er avklart ved ferdigstillelsen
(se human-in-loop-mappen for sak #3 for begrunnelsene):

* Exit-kode ``0/1/2`` beholdes, men reelle avvik (exit 1) vinner over exit 2
  når referansefilene mangler — manglende referanse skal ikke maskere reelle
  avvik.
* Output-format: fritekst som standard, ``--json`` som tillegg for
  automatiserte kontroller.
* Pre-commit-hooken gjelder Python-lintingen. Rust-repoer sjekkes fortsatt for
  ``tests/lint.rs`` under ``cargo test`` (personlig-py#8: leveransen «står
  foreløpig uendret»).
* Meta-privats egne underkataloger (``tests/``, ``docs/``, ``scripts/``)
  oppdages som repoer, og hooken installeres på eierens git-repo — for dem er
  det meta-privat selv.
* En eksisterende hook som ikke driver Python-linting (for eksempel
  markdownlint) overskrives med referansekopien (avklaring 4 og 8), ikke bare
  aktiveres — men fjerner hooken annen linting (markdownlint/cspell),
  varsles det eksplisitt og avklaring med mennesket kreves før
  fiks-kommandoen kjøres (sak #14 punkt 3).
* En ``exclude``-innstilling i ruff-konfigurasjonen (for eksempel
  ``exclude = ["old"]`` i investment-oslo) varsles eksplisitt: fiks-kommandoen
  fjerner den, og avklaring med mennesket kreves før den kjøres
  (sak #14 punkt 4).

Skriptet tas ikke i bruk i automatiserte kontroller før mennesket
eksplisitt godkjenner det (krav i sak #11 punkt 5, sak #14 punkt 2).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

PYTHON_GAMMEL_TEST = ("tests/test_lint.py", "test/test_lint.py")
RUST_TESTER = ("tests/lint.rs", "test/lint.rs")
PYTHON_REFERANSE_REPO = "utilities-py"
RUST_REFERANSE_REPO = "personlig-py"
PYTHON_REFERANSE_STI = ("hooks", "pre-commit")
RUST_KONFIGFILER = ("clippy.toml", ".clippy.toml", "rustfmt.toml", ".rustfmt.toml")
RUFF_KONFIGFILER = ("ruff.toml", ".ruff.toml")

# Faktisk TOML-nøkkel `exclude` (eller `extend-exclude`), eventuelt sitert,
# etterfulgt av `=`. Case-sensitiv: TOML-nøkler er case-sensitive og ruff
# kjenner bare små bokstaver. Ankret til linjestart slik at variabelnavn
# (`my_exclude`), verdier (`ignore = ["exclude"]`) og inline-kommentarer
# (`line-length = 100 # exclude ...`) ikke matcher (sak #14 punkt 4).
EXCLUDE_NOKKEL = re.compile(r"""^\s*["']?(extend-)?exclude["']?\s*=""")


KLASSE_PYTHON = "python"
KLASSE_RUST = "rust"
KLASSE_BEGGE = "begge"
KLASSE_INGEN = "ingen"

KLASSE_VISNING = {
    KLASSE_PYTHON: "Python",
    KLASSE_RUST: "Rust",
    KLASSE_BEGGE: "Python og Rust",
    KLASSE_INGEN: "ingen kode",
}

STATUS_OK = "OK"
STATUS_MANGLER = "mangler"
STATUS_AVVIK = "avvik"
STATUS_INTET = "intet å gjøre"

HOPP_OVER = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        "target",
        "node_modules",
        ".cache",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        "dist",
        "build",
    }
)

E501 = "E501"


class SkriptError(Exception):
    """Feil som gjør at skriptet ikke kan fullføre sjekkene."""


@dataclass
class Funn:
    """Ett avvik eller en mangel funnet i et repo, med fiks-kommandoer."""

    status: str
    tekst: str
    fiks: list[str] = field(default_factory=list)


@dataclass
class Reposultat:
    """Status og funn for ett repo."""

    navn: str
    sti: Path
    klassifisering: str
    funn: list[Funn] = field(default_factory=list)
    hoppet: list[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        """Samlet status: intet å gjøre, mangler, avvik eller OK.

        Mangler (det som skal på plass finnes ikke) prioriteres foran avvik,
        slik at en manglende pre-commit-hook eller lint-test alltid rapporteres
        som mangler.
        """
        if self.klassifisering == KLASSE_INGEN:
            return STATUS_INTET
        if any(f.status == STATUS_MANGLER for f in self.funn):
            return STATUS_MANGLER
        if any(f.status == STATUS_AVVIK for f in self.funn):
            return STATUS_AVVIK
        return STATUS_OK


@dataclass
class Referanser:
    """Stier til referansefilene fra sak #2 (Python) og sak #8 (Rust)."""

    python_hook: Path | None = None
    rust_test: Path | None = None

    @property
    def mangler(self) -> list[str]:
        """Beskrivelse av referansefilene som ikke finnes."""
        mangler = []
        if self.python_hook is None:
            mangler.append(
                f"{PYTHON_REFERANSE_REPO}/{'/'.join(PYTHON_REFERANSE_STI)} (utilities-py sak #2)"
            )
        if self.rust_test is None:
            mangler.append(f"{RUST_REFERANSE_REPO}/tests/lint.rs (personlig-py sak #8)")
        return mangler


@dataclass
class RuffKilde:
    """Én ruff-konfigurasjonskilde: ruff.toml, .ruff.toml eller [tool.ruff]."""

    navn: str
    sti: Path
    er_pyproject: bool
    er_standard: bool


def bygg_parser() -> argparse.ArgumentParser:
    """Bygg argumentleseren for skriptet."""
    parser = argparse.ArgumentParser(
        description=(
            "Sjekk at linting er på plass i alle repoer under meta-privat. "
            "Skriptet endrer aldri repoene — det skriver ut fiks-kommandoer."
        ),
        epilog=(
            "Exit-kode: 0 = alt OK, 1 = minst ett avvik eller mangler, "
            "2 = ingen reelle avvik, men sjekkene kunne ikke fullføres. "
            "Reelle avvik (1) vinner over 2."
        ),
    )
    parser.add_argument(
        "--repo-rot",
        metavar="STI",
        help=(
            "katalogen som inneholder repoene, ett nivå av underkataloger "
            "(standard: META_PRIVAT_ROT, ellers ~/meta-privat)"
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="skriv rapporten som maskinlesbart JSON i stedet for fritekst",
    )
    return parser


def finn_repo_rot(oppgitt: str | None) -> Path:
    """Finn katalogen som inneholder repoene.

    Rekkefølge: --repo-rot, miljøvariabelen META_PRIVAT_ROT, deretter
    ~/meta-privat (menneskevedtak i utilities-py#11).
    """
    for kandidat in (
        oppgitt,
        os.environ.get("META_PRIVAT_ROT"),
        Path.home() / "meta-privat",
    ):
        if not kandidat:
            continue
        rot = Path(kandidat)
        if rot.is_dir():
            return rot
        if oppgitt or os.environ.get("META_PRIVAT_ROT"):
            raise SkriptError(f"Repo-rot {rot} er ikke en katalog.")
    raise SkriptError(
        "Fant ikke meta-privat. Oppgi --repo-rot eller sett META_PRIVAT_ROT."
    )


def finn_reponavn(repo_rot: Path) -> list[str]:
    """Alle underkataloger ett nivå under repo-rota (menneskevedtak i #11)."""
    return sorted(
        katalog.name
        for katalog in repo_rot.iterdir()
        if katalog.is_dir()
        and katalog.name[:1] != "."
        and katalog.name not in HOPP_OVER
    )


def finn_referanser(repo_rot: Path) -> Referanser:
    """Finn referansefilene fra sak #2 og sak #8 under repo-rota."""
    python_hook = repo_rot.joinpath(PYTHON_REFERANSE_REPO, *PYTHON_REFERANSE_STI)
    rust_test = repo_rot / RUST_REFERANSE_REPO / "tests" / "lint.rs"
    return Referanser(
        python_hook=python_hook if python_hook.is_file() else None,
        rust_test=rust_test if rust_test.is_file() else None,
    )


def finn_kildefiler(repo: Path) -> tuple[bool, bool]:
    """Finn ut om repoet inneholder Python- (*.py) og/eller Rust-kode (*.rs)."""
    python = False
    rust = False
    for _rot, kataloger, filer in os.walk(repo):
        kataloger[:] = [k for k in kataloger if k not in HOPP_OVER]
        for filnavn in filer:
            python = python or filnavn.endswith(".py")
            rust = rust or filnavn.endswith(".rs")
        if python and rust:
            break
    return python, rust


def klassifiser(repo: Path) -> str:
    """Klassiser repoet som Python, Rust, begge deler eller ingen kode."""
    har_python_fil, har_rust_fil = finn_kildefiler(repo)
    python = har_python_fil or (repo / "pyproject.toml").is_file()
    rust = har_rust_fil or (repo / "Cargo.toml").is_file()
    if python and rust:
        return KLASSE_BEGGE
    if python:
        return KLASSE_PYTHON
    if rust:
        return KLASSE_RUST
    return KLASSE_INGEN


def les_tekst(sti: Path) -> str:
    """Les en fil som tekst. Returner tom streng hvis filen ikke finnes."""
    try:
        return sti.read_text(encoding="utf-8")
    except OSError:
        return ""


def les_toml(sti: Path) -> dict:
    """Les en TOML-fil. Returner tom ordbok hvis filen mangler eller er ugyldig."""
    try:
        with sti.open("rb") as fil:
            return tomllib.load(fil)
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def les_toml_strengt(sti: Path) -> dict | None:
    """Les en TOML-fil. None hvis filen mangler eller ikke er gyldig TOML."""
    try:
        with sti.open("rb") as fil:
            return tomllib.load(fil)
    except (OSError, tomllib.TOMLDecodeError):
        return None


def finn_testfil(repo: Path, navn: tuple[str, ...]) -> Path | None:
    """Finn en testfil. tests/ og test/ aksepteres begge som testkatalog."""
    for kandidat in navn:
        sti = repo / kandidat
        if sti.is_file():
            return sti
    return None


# --- git pre-commit-hook ---


def finn_git_rot(sti: Path) -> Path | None:
    """Finn arbeidsområdet (git-repoet) som eier stien, eller None.

    Hooken er en egenskap ved git-repoet, ikke ved den enkelte katalogen:
    en katalog som ligger inne i et større git-repo dekkes av hooken der.
    """
    for kandidat in (sti, *sti.parents):
        if (kandidat / ".git").exists():
            return kandidat
    return None


def finn_git_dir(git_rot: Path) -> Path | None:
    """Finn .git-katalogen for arbeidsområdet (støtter gitdir-peker for worktrees)."""
    git = git_rot / ".git"
    if git.is_dir():
        return git
    if git.is_file():
        for linje in les_tekst(git).splitlines():
            if linje.startswith("gitdir:"):
                sti = Path(linje.split(":", 1)[1].strip())
                return sti if sti.is_absolute() else git_rot / sti
    return None


def kjor_git(git_rot: Path, *argumenter: str) -> str | None:
    """Kjør en skrivebeskyttet git-kommando i git-repoet. Returner stdout, eller None."""
    try:
        resultat = subprocess.run(
            ["git", "-C", str(git_rot), *argumenter],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if resultat.returncode != 0:
        return None
    return resultat.stdout.strip()


def finn_hooks_dir(git_rot: Path) -> Path | None:
    """Katalogen git faktisk bruker for hooks — core.hooksPath på alle nivåer.

    ``git rev-parse --git-path hooks`` gir katalogen git vil lete etter hooks
    i: ``core.hooksPath`` fra lokal, global og system-konfigurasjon (f.eks. fra
    dotfiles), ellers ``.git/hooks``. Bare lokal konfigurasjon er ikke nok —
    en globalt aktivert hook kjører også for dette repoet. Relative stier
    løses mot arbeidsområdet, slik git gjør når hooken kjøres. Uten git
    tilgjengelig brukes ``.git/hooks``.
    """
    ut = kjor_git(git_rot, "rev-parse", "--git-path", "hooks")
    if ut:
        sti = Path(ut)
        return sti if sti.is_absolute() else git_rot / sti
    git_dir = finn_git_dir(git_rot)
    return None if git_dir is None else git_dir / "hooks"


def finn_aktiv_hook(git_rot: Path) -> Path | None:
    """Pre-commit-hooken git faktisk vil kjøre, eller None."""
    hooks_dir = finn_hooks_dir(git_rot)
    if hooks_dir is None:
        return None
    hook = hooks_dir / "pre-commit"
    return hook if hook.is_file() else None


def hook_kjorer_linting(innhold: str) -> bool:
    """Sann hvis hooken kjører ruff (Python-linting)."""
    return "ruff" in innhold


# --- fiks-kommandoer ---


def kopi_kommando(kilde: Path, maal: Path) -> str:
    """Kommando som kopierer en referansefil uendret til målet."""
    return (
        f"mkdir -p {shlex.quote(str(maal.parent))} && "
        f"cp {shlex.quote(str(kilde))} {shlex.quote(str(maal))}"
    )


def fjern_kommando(sti: Path) -> str:
    """Kommando som fjerner en fil."""
    return f"rm {shlex.quote(str(sti))}"


def installer_hook_kommando(kilde: Path | None, git_rot: Path) -> str | None:
    """Kommando som kopierer pre-commit-hooken inn i git-repoet og aktiverer den."""
    if kilde is None:
        return None
    maal = git_rot.joinpath(*PYTHON_REFERANSE_STI)
    return (
        f"{kopi_kommando(kilde, maal)} && "
        f"chmod +x {shlex.quote(str(maal))} && "
        f"git -C {shlex.quote(str(git_rot))} config core.hooksPath hooks"
    )


def aktiver_hook_kommando(git_rot: Path) -> str:
    """Kommando som gjør en eksisterende hooks/pre-commit kjørbar og aktiv."""
    maal = git_rot.joinpath(*PYTHON_REFERANSE_STI)
    return (
        f"chmod +x {shlex.quote(str(maal))} && "
        f"git -C {shlex.quote(str(git_rot))} config core.hooksPath hooks"
    )


def stripp_toml_seksjon_kommando(sti: Path, bevar_e501: bool = True) -> str:
    """Kommando som fjerner [tool.ruff]-seksjonene fra pyproject.toml.

    Med ``bevar_e501`` (standard) bevares E501-unntaket: «Ignore E501 skal
    videre føres overalt» (utilities-py#11) — kommandoen leter selv etter
    E501-unntaket i seksjonene som fjernes, og skriver det tilbake som eneste
    gjenværende innstilling. Uten E501-unntak fjernes seksjonene helt — ruff
    default håndhever ikke E501.

    ``bevar_e501=False`` brukes når pyproject.toml er en overskytende
    ruff-konfigurasjon som fjernes helt (flere konfigurasjoner samtidig):
    E501-unntaket beholdes bare i kilden som blir igjen.
    """
    monster = r"(?ms)^\[tool\.ruff(?:\.[^]]*)?\].*?(?=^\[|\Z)"
    if not bevar_e501:
        return (
            'python3 -c "import re,sys,pathlib; '
            "p=pathlib.Path(sys.argv[1]); "
            "t=p.read_text(encoding='utf-8'); "
            f"t=re.sub(r'{monster}', '', t); "
            "p.write_text(t, encoding='utf-8')\" "
            f"{shlex.quote(str(sti))}"
        )
    return (
        'python3 -c "import re,sys,pathlib; '
        "p=pathlib.Path(sys.argv[1]); "
        "t=p.read_text(encoding='utf-8'); "
        f"blokk=re.findall(r'{monster}', t); "
        f"e501=any('{E501}' in b for b in blokk); "
        f"t=re.sub(r'{monster}', '', t); "
        "t=t+chr(10)+'[tool.ruff.lint]'+chr(10)+'ignore = ['"
        f"+chr(34)+'{E501}'+chr(34)+']'+chr(10) if e501 else t; "
        f"p.write_text(t, encoding='utf-8')\" "
        f"{shlex.quote(str(sti))}"
    )


def skriv_om_ruff_toml_kommando(sti: Path) -> str:
    """Kommando som erstatter ruff.toml med kun E501-unntaket, eller fjerner filen.

    Som for [tool.ruff] bevares E501-unntaket (utilities-py#11). Uten unntak
    fjernes filen, slik at ruff default gjelder.
    """
    return (
        'python3 -c "import sys,pathlib; '
        "p=pathlib.Path(sys.argv[1]); "
        "t=p.read_text(encoding='utf-8'); "
        f"e501='{E501}' in t; "
        "t='[lint]'+chr(10)+'ignore = ['+chr(34)"
        f"+'{E501}'+chr(34)+']'+chr(10) if e501 else ''; "
        "p.write_text(t, encoding='utf-8') if e501 else p.unlink()\" "
        f"{shlex.quote(str(sti))}"
    )


def stripp_lints_kommando(sti: Path) -> str:
    """Kommando som fjerner [lints]-innstillingene fra Cargo.toml."""
    seksjon = r"(?ms)^\[\[?(?:workspace\.)?lints(?:\.[^]]*)?\]\]?.*?(?=^\[|\Z)"
    nokkel = r"(?m)^\s*lints(?:\.[A-Za-z0-9_.-]+)?\s*=.*\n?"
    return (
        'python3 -c "import re,sys,pathlib; '
        "p=pathlib.Path(sys.argv[1]); "
        "t=p.read_text(encoding='utf-8'); "
        f"t=re.sub(r'{seksjon}', '', t); "
        f"t=re.sub(r'{nokkel}', '', t); "
        f"p.write_text(t, encoding='utf-8')\" "
        f"{shlex.quote(str(sti))}"
    )


# --- visning av dagens konfigurasjon ---


def innrykk(tekst: str, prefiks: str = "        ") -> str:
    """Rykk inn hver linje i teksten, til visning av dagens konfigurasjon."""
    linjer = tekst.rstrip("\n").splitlines()
    return "\n".join(prefiks + linje if linje else linje for linje in linjer)


def finn_toml_seksjoner(tekst: str, prefiks: str) -> str:
    """Hent ut rå tekst for TOML-seksjoner som starter med prefiks (f.eks. [tool.ruff)."""
    treff = []
    aktiv = False
    for linje in tekst.splitlines():
        if linje.startswith("["):
            aktiv = linje.startswith(prefiks)
        if aktiv:
            treff.append(linje.rstrip())
    return "\n".join(treff)


def er_lints_seksjon(linje: str) -> bool:
    """Sann hvis linja i Cargo.toml åpner en [lints]-seksjon (eventuelt [[lints]])."""
    strip = linje.strip()
    if not strip.startswith("["):
        return False
    navn = strip.lstrip("[").split("]")[0].strip()
    return navn in ("lints", "workspace.lints") or navn.startswith(
        ("lints.", "workspace.lints.")
    )


def er_lints_nokkel(linje: str) -> bool:
    """Sann hvis linja i Cargo.toml setter en lints-nøkkel utenfor [lints]-seksjonene."""
    strip = linje.strip()
    if not strip or strip.startswith(("#", "[")):
        return False
    return strip.startswith(("lints.", "lints ", "lints="))


def finn_lints_innhold(tekst: str) -> str:
    """Hent ut [lints]-innstillingene i Cargo.toml.

    Seksjonene tas med med sitt fulle innhold (for eksempel instillingene
    inne i [lints.clippy]), i tillegg til løse lints-nøkler utenfor seksjonene.
    """
    treff: list[str] = []
    i_lints_seksjon = False
    for linje in tekst.splitlines():
        strip = linje.strip()
        if strip.startswith("["):
            i_lints_seksjon = er_lints_seksjon(linje)
            if i_lints_seksjon:
                treff.append(linje.rstrip())
            continue
        if i_lints_seksjon:
            if strip:
                treff.append(linje.rstrip())
        elif er_lints_nokkel(linje):
            treff.append(linje.rstrip())
    return "\n".join(treff)


# --- sjekker ---


def er_ruff_oppsett_standard(data: dict) -> bool:
    """Sann hvis ruff-oppsettet er default, eventuelt kun E501-unntaket.

    Standarden er default-regelsett uten egen konfigurasjon (utilities-py#7:
    «Bruk standard», «forsøk med default»). Det eneste tillatte tillegget er
    E501-unntaket (utilities-py#11: «Ignore E501 skal videre føres overalt»).
    """
    if not data:
        return True
    if set(data) - {"lint"}:
        return False
    lint = data.get("lint", {})
    if not isinstance(lint, dict) or set(lint) - {"ignore", "extend-ignore"}:
        return False
    for nokkel in ("ignore", "extend-ignore"):
        if nokkel in lint and lint[nokkel] != [E501]:
            return False
    return True


def sjekk_python_konfig(repo: Path) -> list[Funn]:
    """Sjekk at ruff-konfigurasjonen er standarden (default, ev. kun E501-unntak).

    Flere ruff-konfigurasjoner samtidig er et avvik i seg selv: én beholdes
    (den første standardkilden, ellers den første), og fiks-kommandoene
    fjerner de overskytende — også når hver kilde for seg er standard, ellers
    ville avviket stått igjen ved neste kjøring.
    """
    detaljer: list[str] = []
    kilder: list[RuffKilde] = []
    for navn in RUFF_KONFIGFILER:
        sti = repo / navn
        if not sti.is_file():
            continue
        data = les_toml_strengt(sti)
        er_standard = data is not None and er_ruff_oppsett_standard(data)
        kilder.append(
            RuffKilde(navn=navn, sti=sti, er_pyproject=False, er_standard=er_standard)
        )
        if not er_standard:
            tekst = (
                f"{navn} avviker fra standarden (ruff default, eventuelt kun "
                f"{E501}-unntak). Dagens innhold:\n{innrykk(les_tekst(sti))}"
            )
            advarsel = exclude_advarsel(les_tekst(sti))
            if advarsel is not None:
                tekst += f"\n{advarsel}"
            detaljer.append(tekst)
    pyproject = repo / "pyproject.toml"
    blokk = finn_toml_seksjoner(les_tekst(pyproject), "[tool.ruff")
    if blokk:
        data = les_toml_strengt(pyproject)
        ruff_data = (
            data.get("tool", {}).get("ruff", {}) if isinstance(data, dict) else None
        )
        er_standard = isinstance(ruff_data, dict) and er_ruff_oppsett_standard(
            ruff_data
        )
        kilder.append(
            RuffKilde(
                navn="pyproject.toml",
                sti=pyproject,
                er_pyproject=True,
                er_standard=er_standard,
            )
        )
        if not er_standard:
            tekst = (
                "pyproject.toml har [tool.ruff]-konfigurasjon som avviker fra "
                f"standarden (ruff default, eventuelt kun {E501}-unntak, "
                "avklaring 8). Dagens innhold:\n" + innrykk(blokk)
            )
            advarsel = exclude_advarsel(blokk)
            if advarsel is not None:
                tekst += f"\n{advarsel}"
            detaljer.append(tekst)
    if not detaljer and len(kilder) <= 1:
        return []

    fiks: list[str] = []
    if len(kilder) > 1:
        behold = next((kilde for kilde in kilder if kilde.er_standard), kilder[0])
        detaljer.append(
            "Flere ruff-konfigurasjoner finnes samtidig (ruff.toml/.ruff.toml og "
            "[tool.ruff] i pyproject.toml) — de kjemper om hvilken som gjelder. "
            f"Behold {behold.navn}; fiks-kommandoene fjerner de overskytende "
            "kildene, slik at bare én står igjen."
        )
        for kilde in kilder:
            if kilde is behold:
                continue
            fiks.append(
                stripp_toml_seksjon_kommando(kilde.sti, bevar_e501=False)
                if kilde.er_pyproject
                else fjern_kommando(kilde.sti)
            )
    else:
        behold = kilder[0]
    if not behold.er_standard:
        fiks.append(
            stripp_toml_seksjon_kommando(behold.sti)
            if behold.er_pyproject
            else skriv_om_ruff_toml_kommando(behold.sti)
        )
    return [
        Funn(
            STATUS_AVVIK,
            "Lint-konfigurasjonen er ikke standarden (ruff default uten egen "
            f"konfigurasjon, med {E501} ignorert).\n" + "\n".join(detaljer),
            fiks,
        )
    ]


def sjekk_rust_konfig(repo: Path) -> list[Funn]:
    """Sjekk at rustfmt/clippy-oppsettet er standarden fra personlig-py sak #8."""
    detaljer: list[str] = []
    fiks: list[str] = []
    for navn in RUST_KONFIGFILER:
        sti = repo / navn
        if sti.is_file():
            detaljer.append(
                f"konfig-filen {navn} finnes i crate-roten. "
                f"Dagens innhold:\n{innrykk(les_tekst(sti))}"
            )
            fiks.append(fjern_kommando(sti))
    cargo_sti = repo / "Cargo.toml"
    innhold = finn_lints_innhold(les_tekst(cargo_sti))
    if innhold:
        detaljer.append(
            f"Cargo.toml har [lints]-innstillinger. Dagens innhold:\n{innrykk(innhold)}"
        )
        fiks.append(stripp_lints_kommando(cargo_sti))
    if not detaljer:
        return []
    return [
        Funn(
            STATUS_AVVIK,
            "Lint-konfigurasjonen er ikke standarden fra personlig-py sak #8 "
            "(standard konfigurasjon, uten konfig-filer og [lints]-innstillinger).\n"
            + "\n".join(detaljer),
            fiks,
        )
    ]


def trenger_overskriving(innhold: str, referanse: Path | None) -> bool:
    """Sann hvis hooken ikke kjører ruff eller avviker fra referansefilen."""
    return not hook_kjorer_linting(innhold) or (
        referanse is not None and innhold != les_tekst(referanse)
    )


def annen_linting_advarsel(innhold: str) -> str | None:
    """Advarsel hvis hooken driver annen linting som overskriving fjerner.

    `dokumentasjon` har i dag en markdownlint/cspell-hook: fiks-kommandoen
    overskriver den med ruff-referansen, og fjerner dermed stave- og
    markdown-kontrollen. Avklar med mennesket (sak #14 punkt 3) om den
    skal beholdes før fiks-kommandoen kjøres.
    """
    lav = innhold.lower()
    if "markdownlint" in lav or "cspell" in lav:
        return (
            "MERK: overskrivingen fjerner markdownlint/cspell-dekningen som "
            "hooken har i dag. Avklar med mennesket (sak #14 punkt 3) om "
            "stave- og markdown-kontrollen skal beholdes (for eksempel "
            "kombinert hook eller kjøring utenfor hooken) før "
            "fiks-kommandoen kjøres."
        )
    return None


def exclude_advarsel(tekst: str) -> str | None:
    """Advarsel hvis ruff-konfigurasjonen har exclude som fiks-kommandoen fjerner.

    `investment-oslo` har `exclude = ["old"]` for arkivert kode
    (jf. slegga/investment-oslo#27): fiks-kommandoen fjerner filen fordi
    den ikke inneholder E501, slik at `old/` blir lintet ved neste kjøring.
    Avklar med mennesket (sak #14 punkt 4) om `exclude` skal bevares før
    filen fjernes.

    Sjekker faktisk TOML-nøkkel (`exclude` eller `extend-exclude`, eventuelt
    sitert): delstrenger i variabelnavn, verdier og kommentarer varsler ikke.
    """
    for linje in tekst.splitlines():
        kode, _, _ = linje.partition("#")
        if EXCLUDE_NOKKEL.match(kode):
            return (
                "MERK: fiks-kommandoen fjerner `exclude` som holder arkivert "
                "kode utenfor ruff (for eksempel `old/` i investment-oslo). "
                "Avklar med mennesket (sak #14 punkt 4) om `exclude` skal "
                "bevares før fiks-kommandoen kjøres — ellers blir den "
                "ekskluderte koden lintet ved neste kjøring."
            )
    return None


def sjekk_hook_innhold(
    maal: Path,
    referanse: Path | None,
    referanse_mangler: str,
    overskriv_fiks: list[str],
) -> list[Funn]:
    """Sjekk at pre-commit-hooken er kjørbar, kjører ruff og er referansefilen uendret.

    Innholdssjekkene kjøres uavhengig av om hooken er aktivert (avklaring 4):
    en hook som ikke driver Python-linting skal overskrives med
    referansekopien, ikke bare aktiveres.
    """
    funn: list[Funn] = []
    innhold = les_tekst(maal)
    if not os.access(maal, os.X_OK):
        funn.append(
            Funn(
                STATUS_AVVIK,
                f"Pre-commit-hooken {maal} er ikke kjørbar, og blir derfor hoppet "
                "over av git — linting skjer ikke ved commit.",
                [f"chmod +x {shlex.quote(str(maal))}"],
            )
        )
    if not hook_kjorer_linting(innhold):
        tekst = (
            f"Pre-commit-hooken {maal} kjører ikke ruff. Linting for Python skal "
            "skje via pre-commit-hooken (menneskevedtak i utilities-py#7/#11). "
            f"Dagens innhold:\n{innrykk(innhold)}"
        )
        advarsel = annen_linting_advarsel(innhold)
        if advarsel is not None:
            tekst += f"\n{advarsel}"
        if referanse is None:
            tekst += " " + referanse_mangler
        funn.append(Funn(STATUS_AVVIK, tekst, overskriv_fiks))
    elif referanse is not None and innhold != les_tekst(referanse):
        tekst = (
            f"Innholdet i {maal} avviker fra referansen i "
            f"{PYTHON_REFERANSE_REPO}/{'/'.join(PYTHON_REFERANSE_STI)}. Hooken "
            "skal kopieres uendret (avklaring 4) — overskriv med referansekopien. "
            f"Dagens innhold:\n{innrykk(innhold)}"
        )
        advarsel = annen_linting_advarsel(innhold)
        if advarsel is not None:
            tekst += f"\n{advarsel}"
        funn.append(
            Funn(
                STATUS_AVVIK,
                tekst,
                overskriv_fiks,
            )
        )
    return funn


def sjekk_precommit(git_rot: Path | None, refs: Referanser) -> list[Funn]:
    """Sjekk at linting skjer via git pre-commit-hook (menneskevedtak i #7/#11).

    Når hooks/pre-commit finnes uten å være aktivert, vurderes innholdet mot
    referansen likevel (avklaring 4): fiks-kommandoen «Aktiver den» skal ikke
    kunne aktivere en hook som ikke driver Python-linting — da overskrives
    hooken med referansekopien i stedet.
    """
    if git_rot is None:
        return [
            Funn(
                STATUS_MANGLER,
                "Pre-commit-hooken mangler: katalogen ligger ikke i noe git-repo, "
                "og linting kan derfor ikke skje ved git commit. Flytt koden inn "
                "i et git-repo.",
                [],
            )
        ]
    referanse_mangler = ""
    fiks: list[str] = []
    if refs.python_hook is not None:
        fiks = [k for k in [installer_hook_kommando(refs.python_hook, git_rot)] if k]
    else:
        referanse_mangler = (
            f"Referansefilen {PYTHON_REFERANSE_REPO}/{'/'.join(PYTHON_REFERANSE_STI)} "
            "(utilities-py sak #2) mangler — kan ikke skrive ut kopieringskommando."
        )
    aktiv = finn_aktiv_hook(git_rot)
    standard = git_rot.joinpath(*PYTHON_REFERANSE_STI)
    if aktiv is None and not standard.is_file():
        tekst = (
            "Pre-commit-hooken mangler: linting skal skje via git pre-commit-hook, "
            "ikke i testkjøringen (menneskevedtak i utilities-py#7/#11). "
            f"Kopier {PYTHON_REFERANSE_REPO}/{'/'.join(PYTHON_REFERANSE_STI)} "
            f"inn i git-repoet {git_rot} og aktiver den."
        )
        if refs.python_hook is None:
            tekst += " " + referanse_mangler
        return [Funn(STATUS_MANGLER, tekst, fiks)]

    maal = aktiv if aktiv is not None else standard
    innholdsfunn = sjekk_hook_innhold(maal, refs.python_hook, referanse_mangler, fiks)
    if aktiv is not None:
        return innholdsfunn

    visning = standard.relative_to(git_rot).as_posix()
    if trenger_overskriving(les_tekst(maal), refs.python_hook):
        tekst = (
            f"{visning} finnes i {git_rot}, men er ikke aktivert som pre-commit-hook "
            "(git kjører den ikke), og innholdet er ikke referansefilen kopiert "
            "uendret (avklaring 4). Overskriv med referansekopien og aktiver den."
        )
        advarsel = annen_linting_advarsel(les_tekst(maal))
        if advarsel is not None:
            tekst += f"\n{advarsel}"
        if refs.python_hook is None:
            tekst += " " + referanse_mangler
        aktivering = Funn(STATUS_AVVIK, tekst, fiks)
    else:
        bekreftelse = (
            "Innholdet er referansefilen kopiert uendret (avklaring 4)."
            if refs.python_hook is not None
            else "Innholdet er ikke kontrollert mot referansen. " + referanse_mangler
        )
        aktivering = Funn(
            STATUS_AVVIK,
            f"{visning} finnes i {git_rot}, men er ikke aktivert som pre-commit-hook "
            "(git kjører den ikke). Aktiver den, for eksempel med "
            f"`git config core.hooksPath hooks`. {bekreftelse}",
            [aktiver_hook_kommando(git_rot)],
        )
    return [aktivering, *innholdsfunn]


def sjekk_testinnhold(
    repo: Path,
    testfil: Path,
    referanse: Path | None,
    referanse_visning: str,
    sak: str,
    resultat: Reposultat,
) -> None:
    """Sjekk at innholdet i lint-testen er referansefilen kopiert uendret (avklaring 4)."""
    if referanse is None:
        resultat.hoppet.append(
            f"innholdet i lint-testen — referansefilen fra {sak} finnes ikke"
        )
        return
    if les_tekst(testfil) != les_tekst(referanse):
        resultat.funn.append(
            Funn(
                STATUS_AVVIK,
                f"Innholdet i {testfil.relative_to(repo).as_posix()} avviker fra "
                f"{referanse_visning}. Testfilen skal kopieres uendret "
                "(avklaring 4) — overskriv med referansekopien.",
                [kopi_kommando(referanse, testfil)],
            )
        )


def sjekk_python(
    repo: Path, git_rot: Path | None, refs: Referanser, resultat: Reposultat
) -> None:
    """Sjekk pre-commit-hook, gammel leveranseform og lint-konfigurasjon for Python."""
    gammel = finn_testfil(repo, PYTHON_GAMMEL_TEST)
    if gammel is not None:
        resultat.funn.append(
            Funn(
                STATUS_AVVIK,
                f"{gammel.relative_to(repo).as_posix()} er gammel leveranseform: "
                "linting skal skje via git pre-commit-hook, ikke i testkjøringen "
                "(menneskevedtak i utilities-py#7/#11). Fjern lint-testen.",
                [fjern_kommando(gammel)],
            )
        )
    resultat.funn.extend(sjekk_precommit(git_rot, refs))
    if refs.python_hook is None:
        resultat.hoppet.append(
            "innholdet i pre-commit-hooken — referansefilen fra sak #2 finnes ikke"
        )
    resultat.funn.extend(sjekk_python_konfig(repo))


def cargo_testmal_stier(cargo: dict) -> list[str]:
    """Stier for eksplisitte [[test]]-mål i Cargo.toml.

    Et [[test]]-mål uten ``path`` peker på ``tests/<name>.rs``.
    """
    stier = []
    for mal in cargo.get("test", []):
        if not isinstance(mal, dict):
            continue
        sti = mal.get("path")
        if isinstance(sti, str):
            stier.append(sti.replace("\\", "/"))
        elif isinstance(mal.get("name"), str):
            stier.append(f"tests/{mal['name']}.rs")
    return stier


def sjekk_cargo_oppdagelse(repo: Path, testfil: Path) -> str | None:
    """Sjekk om cargo test ville kjørt lint-testen. Returner avvikstekst eller None."""
    rel = testfil.relative_to(repo).as_posix()
    cargo = les_toml(repo / "Cargo.toml")
    if rel in cargo_testmal_stier(cargo):
        return None
    if cargo.get("package", {}).get("autotests") is False:
        return (
            f"{rel} ville ikke blitt kjørt av cargo test fordi autotests = false "
            "i Cargo.toml og det ikke finnes et [[test]]-mål som peker på filen"
        )
    if testfil.parent.name == "tests":
        return None
    return (
        f"{rel} er ikke en integrasjonstest under cargo test — cargo finner bare "
        "tester i tests/ eller som [[test]]-mål i Cargo.toml"
    )


def sjekk_rust(repo: Path, refs: Referanser, resultat: Reposultat) -> None:
    """Sjekk lint-test, testkjøring og lint-konfigurasjon for Rust."""
    testfil = finn_testfil(repo, RUST_TESTER)
    if testfil is None:
        tekst = (
            "Lint-testen mangler: tests/lint.rs finnes ikke (test/ aksepteres også)."
        )
        fiks = []
        if refs.rust_test is not None:
            fiks = [kopi_kommando(refs.rust_test, repo / "tests" / "lint.rs")]
        else:
            tekst += " Referansefilen fra sak #8 mangler — kan ikke skrive ut kopieringskommando."
        resultat.funn.append(Funn(STATUS_MANGLER, tekst, fiks))
    else:
        avvik = sjekk_cargo_oppdagelse(repo, testfil)
        if avvik is not None:
            tekst = (
                f"Lint-testen {testfil.relative_to(repo).as_posix()} inngår ikke i "
                f"den lokale testkjøringen: {avvik}."
            )
            fiks = []
            if refs.rust_test is not None:
                maal = repo / "tests" / "lint.rs"
                fiks = [kopi_kommando(refs.rust_test, maal)]
                if maal != testfil:
                    fiks.append(fjern_kommando(testfil))
            resultat.funn.append(Funn(STATUS_AVVIK, tekst, fiks))
        sjekk_testinnhold(
            repo,
            testfil,
            refs.rust_test,
            f"referansen i {RUST_REFERANSE_REPO}/tests/lint.rs",
            "sak #8",
            resultat,
        )
    resultat.funn.extend(sjekk_rust_konfig(repo))


def sjekk_repo(navn: str, sti: Path, refs: Referanser) -> Reposultat:
    """Klassifiser og sjekk ett repo."""
    resultat = Reposultat(navn=navn, sti=sti, klassifisering=klassifiser(sti))
    if resultat.klassifisering == KLASSE_INGEN:
        return resultat
    git_rot = finn_git_rot(sti)
    if resultat.klassifisering in (KLASSE_PYTHON, KLASSE_BEGGE):
        sjekk_python(sti, git_rot, refs, resultat)
    if resultat.klassifisering in (KLASSE_RUST, KLASSE_BEGGE):
        sjekk_rust(sti, refs, resultat)
    return resultat


def skriv_repo(resultat: Reposultat) -> None:
    """Skriv status, funn og fiks-kommandoer for ett repo."""
    print(
        f"{resultat.navn}: {resultat.status} ({KLASSE_VISNING[resultat.klassifisering]})"
    )
    for funn in resultat.funn:
        linjer = funn.tekst.splitlines()
        print(f"  - {linjer[0]}")
        for linje in linjer[1:]:
            print(f"    {linje}" if linje else "")
        if funn.fiks:
            print("    Fiks-kommandoer:")
            for kommando in funn.fiks:
                print(f"      {kommando}")
    for linje in resultat.hoppet:
        print(f"  - Ikke kontrollert: {linje}")


def lag_json_rapport(
    repo_rot: Path,
    refs: Referanser,
    resultater: list[Reposultat],
    telling: dict[str, int],
    exit_kode: int,
) -> str:
    """Bygg rapporten som maskinlesbart JSON for automatiserte kontroller."""
    data = {
        "repo_rot": str(repo_rot),
        "referanser": {
            "python_hook": str(refs.python_hook) if refs.python_hook else None,
            "rust_test": str(refs.rust_test) if refs.rust_test else None,
            "mangler": refs.mangler,
        },
        "repoer": [
            {
                "navn": resultat.navn,
                "sti": str(resultat.sti),
                "klassifisering": resultat.klassifisering,
                "status": resultat.status,
                "funn": [
                    {"status": funn.status, "tekst": funn.tekst, "fiks": funn.fiks}
                    for funn in resultat.funn
                ],
                "hoppet": resultat.hoppet,
            }
            for resultat in resultater
        ],
        "sammendrag": {
            STATUS_OK: telling[STATUS_OK],
            STATUS_MANGLER: telling[STATUS_MANGLER],
            STATUS_AVVIK: telling[STATUS_AVVIK],
            STATUS_INTET: telling[STATUS_INTET],
        },
        "exit_kode": exit_kode,
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


def hoved() -> int:
    """Kjør sjekkene og skriv ut rapporten. Returner exit-kode."""
    args = bygg_parser().parse_args()
    try:
        repo_rot = finn_repo_rot(args.repo_rot)
        reponavn = finn_reponavn(repo_rot)
        refs = finn_referanser(repo_rot)
    except SkriptError as err:
        print(f"Feil: {err}", file=sys.stderr)
        return 2

    if not args.json:
        ord_for_repo = "repo" if len(reponavn) == 1 else "repoer"
        print(f"Sjekker lint-tester i {len(reponavn)} {ord_for_repo} under {repo_rot}")
        print("Repoliste: alle underkataloger ett nivå under repo-rota")
        if refs.python_hook is not None:
            print(
                f"Referanse pre-commit-hook (utilities-py sak #2): {refs.python_hook}"
            )
        if refs.rust_test is not None:
            print(f"Referanse Rust (personlig-py sak #8): {refs.rust_test}")
        for manglende in refs.mangler:
            print(f"ADVARSEL: Referansefilen {manglende} finnes ikke.")
        if refs.mangler:
            print(
                "ADVARSEL: Sjekkene som trenger referansefilene blir hoppet over, "
                "og fiks-kommandoene som kopierer fra referanserepoene kan ikke "
                "skrives ut."
            )
        print()

    telling = {STATUS_OK: 0, STATUS_MANGLER: 0, STATUS_AVVIK: 0, STATUS_INTET: 0}
    resultater: list[Reposultat] = []
    for navn in reponavn:
        resultat = sjekk_repo(navn, repo_rot / navn, refs)
        telling[resultat.status] += 1
        resultater.append(resultat)
        if not args.json:
            skriv_repo(resultat)

    # Reelle avvik vinner over exit-kode 2 (avklart 2026-10-24): manglende
    # referansefiler skal ikke maskere avvik som faktisk er funnet.
    if telling[STATUS_MANGLER] or telling[STATUS_AVVIK]:
        exit_kode = 1
    elif refs.mangler:
        exit_kode = 2
    else:
        exit_kode = 0

    if args.json:
        print(lag_json_rapport(repo_rot, refs, resultater, telling, exit_kode))
        return exit_kode

    print()
    print(
        f"Sammendrag: {telling[STATUS_OK]} {STATUS_OK}, "
        f"{telling[STATUS_MANGLER]} {STATUS_MANGLER}, "
        f"{telling[STATUS_AVVIK]} {STATUS_AVVIK}, "
        f"{telling[STATUS_INTET]} {STATUS_INTET}"
    )
    print(
        "Skriptet endrer ingenting selv — kjør fiks-kommandoene over for å rette avvikene."
    )
    if exit_kode == 1 and refs.mangler:
        print(
            "Avslutter med exit-kode 1 (reelle avvik). Merk at ikke alle sjekker "
            "kunne fullføres — se ADVARSEL over."
        )
    elif exit_kode == 2:
        print(
            "Avslutter med exit-kode 2: ingen reelle avvik funnet, men ikke alle "
            "sjekker kunne fullføres."
        )
    return exit_kode


if __name__ == "__main__":
    sys.exit(hoved())
