#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["PyYAML>=6.0", "tomli>=2.0; python_version < '3.11'"]
# ///
"""Sjekk at lint-testene er på plass i alle repoer i prosjektet.

Skriptet går gjennom repoene i en repoliste og kontrollerer for hvert repo:

* klassifisering: Python, Rust, begge deler eller ingen kode, ut fra
  ``pyproject.toml`` og ``*.py``, ``Cargo.toml`` og ``*.rs``
* at lint-testen er på plass (``tests/test_lint.py`` for Python,
  ``tests/lint.rs`` for Rust — ``test/`` aksepteres også som testkatalog)
* at lint-testen inngår i den lokale testkjøringen (pytest-oppdagelse for
  Python, ``tests/lint.rs`` er integrasjonstest under ``cargo test`` for Rust)
* at innholdet i lint-testen er referansefilen kopiert uendret (avklaring 4)
* at lint-konfigurasjonen er standarden fra referanserepoene (ruff-oppsettet
  fra utilities-py sak #2, rustfmt/clippy-oppsettet fra personlig-py sak #8)

Repoer uten kode rapporteres som intet å gjøre (avklaring 1). Repoer som ikke
er klonet lokalt rapporteres med egen status «ikke klonet» og påvirker ikke
exit-koden.

Skriptet endrer aldri repoene (avklaring 5). For hvert avvik skriver det ut
konkrete kommandoer som fikser avviket når du kjører dem selv — for eksempel
kopiering av testfilene fra referanserepoene uten endringer, og overskriving
av gammel lint-konfigurasjon med standarden (avklaring 8).

## Slik finner skriptet repoene

Uten argumenter leses ``config.yaml`` i meta-privat: ``repogruppe`` peker på
repolista (for eksempel ``repos-all.txt``) og ``repos_dir`` sier hvor repoene
ligger. Plasseringen av meta-privat kan oppgis med ``--meta-rot`` eller
miljøvariabelen ``META_PRIVAT_ROT``, ellers søkes det oppover fra skriptet og
fra arbeidskatalogen. Med ``--repo-rot`` og/eller ``--repo-liste`` kjøres
skriptet mot en annen rot eller liste — for eksempel et fikstur-tre i tester.

## Referansefiler

* Python: ``tests/test_lint.py`` og ``ruff.toml`` i repoet ``utilities-py``
* Rust: ``tests/lint.rs`` i repoet ``personlig-py``

Hvis referansefilene ikke finnes ennå, sier skriptet tydelig ifra om det,
hopper over sjekkene som trenger dem og avslutter med exit-kode 2.

## Exit-kode

* ``0`` — alt OK (eventuelt intet å gjøre i alle repoer)
* ``1`` — minst ett avvik eller mangler
* ``2`` — skriptet kunne ikke fullføre alle sjekkene (fant ikke repolista,
  eller referansefilene fra sak #2/sak #8 mangler)

Repoer som ikke er klonet lokalt (status «ikke klonet») telles i sammendraget,
men påvirker verken exit-kode 1 eller 2: ``repos-all.txt`` inneholder alle
GitHub-repoene, så uregistrerte repoer skal ikke forsure automatiserte
kontroller.

## Avklarte valg

* Meta-privat finnes via ``--meta-rot`` eller miljøvariabelen
  ``META_PRIVAT_ROT``, ellers søkes det oppover fra skriptet og fra
  arbeidskatalogen.
* Exit-kode 2 brukes når referansefilene mangler, slik at automatiserte
  kontroller ikke tror alt er OK når sjekkene ikke kunne fullføres.
* Avvikende lint-konfigurasjon rapporteres med dagens innhold og kommandoer
  som overskriver eller fjerner gammel konfig (avklaring 8).
"""

from __future__ import annotations

import argparse
import configparser
import fnmatch
import os
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

PYTHON_TESTER = ("tests/test_lint.py", "test/test_lint.py")
RUST_TESTER = ("tests/lint.rs", "test/lint.rs")
PYTHON_REFERANSE_REPO = "utilities-py"
RUST_REFERANSE_REPO = "personlig-py"
RUST_KONFIGFILER = ("clippy.toml", ".clippy.toml", "rustfmt.toml", ".rustfmt.toml")
PYTHON_KONFIGFILER = (".ruff.toml",)

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
STATUS_IKKE_KLONET = "ikke klonet"

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

STANDARD_PYTHON_FILES = ("test_*.py", "*_test.py")


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
    ikke_klonet: bool = False

    @property
    def status(self) -> str:
        """Samlet status: ikke klonet, intet å gjøre, OK, mangler eller avvik.

        Repoer som ikke er klonet lokalt får egen status og telles ikke som
        mangler — de skal ikke påvirke exit-koden i automatiserte kontroller.
        Mangler (lint-test som ikke finnes) prioriteres foran avvik, slik at en
        manglende lint-test alltid rapporteres som mangler.
        """
        if self.ikke_klonet:
            return STATUS_IKKE_KLONET
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

    python_test: Path | None = None
    python_config: Path | None = None
    rust_test: Path | None = None

    @property
    def mangler(self) -> list[str]:
        """Beskrivelse av referansefilene som ikke finnes."""
        mangler = []
        if self.python_test is None:
            mangler.append(f"{PYTHON_REFERANSE_REPO}/tests/test_lint.py (utilities-py sak #2)")
        if self.python_config is None:
            mangler.append(f"{PYTHON_REFERANSE_REPO}/ruff.toml (utilities-py sak #2)")
        if self.rust_test is None:
            mangler.append(f"{RUST_REFERANSE_REPO}/tests/lint.rs (personlig-py sak #8)")
        return mangler


@dataclass
class Plassering:
    """Hvor repoene ligger og hvilken repoliste som skal brukes."""

    repo_rot: Path
    liste_sti: Path | None = None


@dataclass
class PytestOppsett:
    """Pytest-oppsett som styrer hvilke testfiler som blir samlet inn."""

    testpaths: list[str] | None = None
    python_files: tuple[str, ...] = STANDARD_PYTHON_FILES


def bygg_parser() -> argparse.ArgumentParser:
    """Bygg argumentleseren for skriptet."""
    parser = argparse.ArgumentParser(
        description=(
            "Sjekk at lint-testene er på plass i alle repoer i prosjektet. "
            "Skriptet endrer aldri repoene — det skriver ut fiks-kommandoer."
        ),
        epilog=(
            "Exit-kode: 0 = alt OK, 1 = minst ett avvik eller mangler, "
            "2 = skriptet kunne ikke fullføre alle sjekkene."
        ),
    )
    parser.add_argument(
        "--meta-rot",
        metavar="STI",
        help="katalog med config.yaml i meta-privat (standard: auto-søk)",
    )
    parser.add_argument(
        "--repo-rot",
        metavar="STI",
        help="katalogen som inneholder repoene (standard: repos_dir i config.yaml)",
    )
    parser.add_argument(
        "--repo-liste",
        metavar="STI",
        help="fil med repo-navn, ett per linje (standard: repogruppe i config.yaml)",
    )
    return parser


def finn_meta_rot(oppgitt: str | None) -> Path | None:
    """Finn katalogen med config.yaml for meta-privat.

    Søkerekkefølge: --meta-rot, miljøvariabelen META_PRIVAT_ROT, deretter
    oppover fra skriptet og fra arbeidskatalogen.
    """
    for eksplisitt in (oppgitt, os.environ.get("META_PRIVAT_ROT")):
        if eksplisitt:
            rot = Path(eksplisitt)
            if (rot / "config.yaml").is_file():
                return rot
            raise SkriptError(f"Finner ikke config.yaml i {rot}.")
    for start in (Path(__file__).resolve().parent, Path.cwd()):
        for kandidat in (start, *start.parents):
            if (kandidat / "config.yaml").is_file():
                return kandidat
    return None


def les_config(meta_rot: Path) -> dict:
    """Les config.yaml i meta-privat (repogruppe og repos_dir)."""
    sti = meta_rot / "config.yaml"
    try:
        data = yaml.safe_load(sti.read_text(encoding="utf-8")) or {}
    except OSError as err:
        raise SkriptError(f"Klarte ikke å lese {sti}: {err}") from err
    if not isinstance(data, dict):
        raise SkriptError(f"{sti} inneholder ikke en nøkkel-verdi-oversikt.")
    return data


def finn_plassering(args: argparse.Namespace) -> Plassering:
    """Finn repo-rot og repoliste.

    Med --repo-rot eller --repo-liste brukes bare argumentene (for eksempel mot
    et fikstur-tre i tester). Uten argumenter leses config.yaml i meta-privat.
    """
    if args.repo_rot or args.repo_liste:
        liste_sti = Path(args.repo_liste) if args.repo_liste else None
        repo_rot = Path(args.repo_rot) if args.repo_rot else liste_sti.parent
        return kontroller_plassering(repo_rot, liste_sti)

    meta_rot = finn_meta_rot(args.meta_rot)
    if meta_rot is None:
        raise SkriptError(
            "Fant ikke meta-privat (config.yaml). Oppgi --meta-rot, sett "
            "META_PRIVAT_ROT, eller bruk --repo-rot/--repo-liste."
        )
    config = les_config(meta_rot)
    liste_sti = None
    repogruppe = config.get("repogruppe")
    if repogruppe:
        kandidat = Path(str(repogruppe))
        liste_sti = kandidat if kandidat.is_absolute() else meta_rot / kandidat
    repos_dir = config.get("repos_dir")
    if repos_dir:
        kandidat = Path(str(repos_dir))
        repo_rot = kandidat if kandidat.is_absolute() else meta_rot / kandidat
        if not repo_rot.is_dir():
            repo_rot = meta_rot
    else:
        repo_rot = meta_rot
    return kontroller_plassering(repo_rot, liste_sti)


def kontroller_plassering(repo_rot: Path, liste_sti: Path | None) -> Plassering:
    """Kontroller at repo-rot og repoliste finnes før bruk."""
    if liste_sti is not None and not liste_sti.is_file():
        raise SkriptError(f"Repolista {liste_sti} finnes ikke.")
    if not repo_rot.is_dir():
        raise SkriptError(f"Repo-rot {repo_rot} er ikke en katalog.")
    return Plassering(repo_rot=repo_rot, liste_sti=liste_sti)


def finn_reponavn(plassering: Plassering) -> list[str]:
    """Hent reponavn fra lista, eller alle underkataloger av repo-rota."""
    if plassering.liste_sti is not None:
        navn = []
        for linje in plassering.liste_sti.read_text(encoding="utf-8").splitlines():
            strip = linje.strip()
            if strip and not strip.startswith("#"):
                navn.append(strip)
        return navn
    return sorted(
        katalog.name
        for katalog in plassering.repo_rot.iterdir()
        if katalog.is_dir() and katalog.name[:1] != "."
    )


def finn_referanser(repo_rot: Path) -> Referanser:
    """Finn referansefilene fra sak #2 og sak #8 under repo-rota."""
    python_test = repo_rot / PYTHON_REFERANSE_REPO / "tests" / "test_lint.py"
    python_config = repo_rot / PYTHON_REFERANSE_REPO / "ruff.toml"
    rust_test = repo_rot / RUST_REFERANSE_REPO / "tests" / "lint.rs"
    return Referanser(
        python_test=python_test if python_test.is_file() else None,
        python_config=python_config if python_config.is_file() else None,
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


def finn_testfil(repo: Path, navn: tuple[str, ...]) -> Path | None:
    """Finn lint-testen. tests/ og test/ aksepteres begge som testkatalog."""
    for kandidat in navn:
        sti = repo / kandidat
        if sti.is_file():
            return sti
    return None


def les_pytest_oppsett(repo: Path) -> PytestOppsett:
    """Les testpaths og python_files fra pytest-oppsettet i repoet.

    Let etter pytest.ini, pyproject.toml, tox.ini og setup.cfg — i den
    rekkefølgen — og bruker den første som finnes.
    """
    ini = repo / "pytest.ini"
    if ini.is_file():
        return les_pytest_ini(ini, "pytest")
    pyproject = repo / "pyproject.toml"
    if pyproject.is_file():
        data = les_toml(pyproject)
        oppsett = data.get("tool", {}).get("pytest", {}).get("ini_options", {})
        testpaths = oppsett.get("testpaths")
        python_files = oppsett.get("python_files")
        return PytestOppsett(
            testpaths=[str(t) for t in testpaths] if isinstance(testpaths, list) else None,
            python_files=til_monstre(python_files),
        )
    tox_ini = repo / "tox.ini"
    if tox_ini.is_file():
        return les_pytest_ini(tox_ini, "pytest")
    setup_cfg = repo / "setup.cfg"
    if setup_cfg.is_file():
        return les_pytest_ini(setup_cfg, "tool:pytest")
    return PytestOppsett()


def til_monstre(verdi: object) -> tuple[str, ...]:
    """Gjør om en python_files-verdi til en tuple med filnavn-mønstre.

    Tom streng, None og andre tomme verdier gir standardmønstrene, i tråd med
    pytest sin egen oppførsel når python_files ikke er satt.
    """
    if isinstance(verdi, str):
        monstre = tuple(verdi.split())
        return monstre or STANDARD_PYTHON_FILES
    if isinstance(verdi, list):
        monstre = tuple(str(v) for v in verdi)
        return monstre or STANDARD_PYTHON_FILES
    return STANDARD_PYTHON_FILES


def les_pytest_ini(sti: Path, seksjon: str) -> PytestOppsett:
    """Les testpaths og python_files fra en ini-fil med pytest-oppsett."""
    parser = configparser.ConfigParser()
    parser.read(sti, encoding="utf-8")
    if not parser.has_section(seksjon):
        return PytestOppsett()
    testpaths = parser.get(seksjon, "testpaths", fallback="").split()
    python_files = parser.get(seksjon, "python_files", fallback=None)
    return PytestOppsett(
        testpaths=testpaths or None,
        python_files=til_monstre(python_files),
    )


def normaliser_sti(sti: str) -> str:
    """Normaliser en sti fra testpaths: bort \\, ./ og / i starten og slutten."""
    normalisert = sti.replace("\\", "/")
    while normalisert.startswith("./"):
        normalisert = normalisert[2:]
    return normalisert.strip("/")


def sjekk_pytest_oppdagelse(repo: Path, testfil: Path) -> str | None:
    """Sjekk om pytest ville samlet inn lint-testen. Returner avvikstekst eller None."""
    oppsett = les_pytest_oppsett(repo)
    if oppsett.testpaths is not None:
        katalog = testfil.parent.relative_to(repo).as_posix()
        inne = any(
            sti in ("", ".") or katalog == sti or katalog.startswith(sti + "/")
            for sti in (normaliser_sti(t) for t in oppsett.testpaths)
        )
        if not inne:
            return (
                f"{testfil.relative_to(repo).as_posix()} ligger utenfor "
                f"testpaths {oppsett.testpaths} i pytest-oppsettet og ville ikke "
                "blitt samlet inn av pytest"
            )
    if not any(fnmatch.fnmatch(testfil.name, monster) for monster in oppsett.python_files):
        return (
            f"filnavnet {testfil.name} matcher ikke python_files "
            f"{list(oppsett.python_files)} i pytest-oppsettet"
        )
    return None


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


def mal_katalog(repo: Path) -> Path:
    """Katalogen der pytest ville funnet testen: første testpath, eller tests/."""
    oppsett = les_pytest_oppsett(repo)
    if oppsett.testpaths:
        return repo / oppsett.testpaths[0]
    return repo / "tests"


def innrykk(tekst: str, prefiks: str = "        ") -> str:
    """Rykk inn hver linje i teksten, til visning av dagens konfigurasjon."""
    linjer = tekst.rstrip("\n").splitlines()
    return "\n".join(prefiks + linje if linje else linje for linje in linjer)


def kopi_kommando(kilde: Path, maal: Path) -> str:
    """Kommando som kopierer en referansefil uendret til målet."""
    return (
        f"mkdir -p {shlex.quote(str(maal.parent))} && "
        f"cp {shlex.quote(str(kilde))} {shlex.quote(str(maal))}"
    )


def fjern_kommando(sti: Path) -> str:
    """Kommando som fjerner en fil med avvikende lint-konfigurasjon."""
    return f"rm {shlex.quote(str(sti))}"


def stripp_toml_seksjon_kommando(sti: Path) -> str:
    """Kommando som fjerner [tool.ruff]-seksjonene fra pyproject.toml."""
    monster = r"(?ms)^\[tool\.ruff(?:\.[^]]*)?\].*?(?=^\[|\Z)"
    return (
        'python3 -c "import re,sys,pathlib; '
        "p=pathlib.Path(sys.argv[1]); "
        "t=p.read_text(encoding='utf-8'); "
        f"p.write_text(re.sub(r'{monster}', '', t), encoding='utf-8')\" "
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
    return navn in ("lints", "workspace.lints") or navn.startswith(("lints.", "workspace.lints."))


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


def sjekk_python_konfig(repo: Path, referanse: Path) -> list[Funn]:
    """Sjekk at ruff-konfigurasjonen er standarden fra utilities-py sak #2."""
    standard = referanse.read_text(encoding="utf-8")
    ruff_sti = repo / "ruff.toml"
    detaljer: list[str] = []
    fiks: list[str] = []
    if not ruff_sti.is_file():
        detaljer.append(
            "ruff.toml mangler — standarden er ruff.toml kopiert uendret fra utilities-py sak #2."
        )
        fiks.append(kopi_kommando(referanse, ruff_sti))
    else:
        dagens = ruff_sti.read_text(encoding="utf-8")
        if dagens != standard:
            detaljer.append(
                "ruff.toml avviker fra standarden fra utilities-py sak #2. "
                f"Dagens innhold:\n{innrykk(dagens)}"
            )
            fiks.append(kopi_kommando(referanse, ruff_sti))
    for navn in PYTHON_KONFIGFILER:
        sti = repo / navn
        if sti.is_file():
            detaljer.append(
                f"konfig-filen {navn} finnes i repo-roten og overstyrer ruff.toml "
                f"(ruff prioriterer {navn} framfor ruff.toml). "
                f"Dagens innhold:\n{innrykk(les_tekst(sti))}"
            )
            fiks.append(fjern_kommando(sti))
    blokk = finn_toml_seksjoner(les_tekst(repo / "pyproject.toml"), "[tool.ruff")
    if blokk:
        detaljer.append(
            "pyproject.toml har [tool.ruff]-konfigurasjon (avvikende konfigurasjon, "
            f"avklaring 8). Dagens innhold:\n{innrykk(blokk)}"
        )
        fiks.append(stripp_toml_seksjon_kommando(repo / "pyproject.toml"))
    if not detaljer:
        return []
    return [
        Funn(
            STATUS_AVVIK,
            "Lint-konfigurasjonen er ikke standarden fra utilities-py sak #2.\n"
            + "\n".join(detaljer),
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
        resultat.hoppet.append(f"innholdet i lint-testen — referansefilen fra {sak} finnes ikke")
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


def sjekk_python(repo: Path, refs: Referanser, resultat: Reposultat) -> None:
    """Sjekk lint-test, testkjøring og lint-konfigurasjon for Python."""
    testfil = finn_testfil(repo, PYTHON_TESTER)
    if testfil is None:
        tekst = "Lint-testen mangler: tests/test_lint.py finnes ikke (test/ aksepteres også)."
        fiks = []
        if refs.python_test is not None:
            fiks = [kopi_kommando(refs.python_test, mal_katalog(repo) / "test_lint.py")]
        else:
            tekst += " Referansefilen fra sak #2 mangler — kan ikke skrive ut kopieringskommando."
        resultat.funn.append(Funn(STATUS_MANGLER, tekst, fiks))
    else:
        avvik = sjekk_pytest_oppdagelse(repo, testfil)
        if avvik is not None:
            tekst = (
                f"Lint-testen {testfil.relative_to(repo).as_posix()} inngår ikke i "
                f"den lokale testkjøringen: {avvik}."
            )
            fiks = []
            if refs.python_test is not None:
                maal = mal_katalog(repo) / "test_lint.py"
                fiks = [kopi_kommando(refs.python_test, maal)]
                if maal != testfil:
                    fiks.append(fjern_kommando(testfil))
            resultat.funn.append(Funn(STATUS_AVVIK, tekst, fiks))
        sjekk_testinnhold(
            repo,
            testfil,
            refs.python_test,
            f"referansen i {PYTHON_REFERANSE_REPO}/tests/test_lint.py",
            "sak #2",
            resultat,
        )
    if refs.python_config is None:
        resultat.hoppet.append(
            "lint-konfigurasjonen (ruff.toml) — referansefilen fra sak #2 finnes ikke"
        )
    else:
        resultat.funn.extend(sjekk_python_konfig(repo, refs.python_config))


def sjekk_rust(repo: Path, refs: Referanser, resultat: Reposultat) -> None:
    """Sjekk lint-test, testkjøring og lint-konfigurasjon for Rust."""
    testfil = finn_testfil(repo, RUST_TESTER)
    if testfil is None:
        tekst = "Lint-testen mangler: tests/lint.rs finnes ikke (test/ aksepteres også)."
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
    if not sti.is_dir():
        return Reposultat(
            navn=navn,
            sti=sti,
            klassifisering=KLASSE_INGEN,
            ikke_klonet=True,
            hoppet=[
                f"repo-katalogen {sti} finnes ikke — ikke klonet lokalt, "
                "kan ikke sjekke lint-testene"
            ],
        )
    resultat = Reposultat(navn=navn, sti=sti, klassifisering=klassifiser(sti))
    if resultat.klassifisering == KLASSE_INGEN:
        return resultat
    if resultat.klassifisering in (KLASSE_PYTHON, KLASSE_BEGGE):
        sjekk_python(sti, refs, resultat)
    if resultat.klassifisering in (KLASSE_RUST, KLASSE_BEGGE):
        sjekk_rust(sti, refs, resultat)
    return resultat


def skriv_repo(resultat: Reposultat) -> None:
    """Skriv status, funn og fiks-kommandoer for ett repo."""
    if resultat.ikke_klonet:
        print(f"{resultat.navn}: {resultat.status} (ikke klonet lokalt)")
    else:
        print(f"{resultat.navn}: {resultat.status} ({KLASSE_VISNING[resultat.klassifisering]})")
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


def hoved() -> int:
    """Kjør sjekkene og skriv ut rapporten. Returner exit-kode."""
    args = bygg_parser().parse_args()
    try:
        plassering = finn_plassering(args)
        reponavn = finn_reponavn(plassering)
        refs = finn_referanser(plassering.repo_rot)
    except SkriptError as err:
        print(f"Feil: {err}", file=sys.stderr)
        return 2

    if plassering.liste_sti is not None:
        kilde = f"Repoliste: {plassering.liste_sti}"
    else:
        kilde = "Repoliste: alle underkataloger av repo-rota"
    ord_for_repo = "repo" if len(reponavn) == 1 else "repoer"
    print(f"Sjekker lint-tester i {len(reponavn)} {ord_for_repo} under {plassering.repo_rot}")
    print(f"{kilde}")
    if refs.python_test is not None and refs.python_config is not None:
        print(f"Referanse Python (utilities-py sak #2): {refs.python_test.parent.parent}")
    if refs.rust_test is not None:
        print(f"Referanse Rust (personlig-py sak #8): {refs.rust_test}")
    for manglende in refs.mangler:
        print(f"ADVARSEL: Referansefilen {manglende} finnes ikke.")
    if refs.mangler:
        print(
            "ADVARSEL: Sjekkene som trenger referansefilene blir hoppet over, "
            "og fiks-kommandoene som kopierer fra referanserepoene kan ikke skrives ut."
        )
    print()

    telling = {
        STATUS_OK: 0,
        STATUS_MANGLER: 0,
        STATUS_AVVIK: 0,
        STATUS_INTET: 0,
        STATUS_IKKE_KLONET: 0,
    }
    for navn in reponavn:
        resultat = sjekk_repo(navn, plassering.repo_rot / navn, refs)
        telling[resultat.status] += 1
        skriv_repo(resultat)

    print()
    print(
        f"Sammendrag: {telling[STATUS_OK]} {STATUS_OK}, "
        f"{telling[STATUS_MANGLER]} {STATUS_MANGLER}, "
        f"{telling[STATUS_AVVIK]} {STATUS_AVVIK}, "
        f"{telling[STATUS_INTET]} {STATUS_INTET}, "
        f"{telling[STATUS_IKKE_KLONET]} {STATUS_IKKE_KLONET}"
    )
    print("Skriptet endrer ingenting selv — kjør fiks-kommandoene over for å rette avvikene.")
    if refs.mangler:
        print("Avslutter med exit-kode 2 fordi ikke alle sjekker kunne fullføres.")
        return 2
    if telling[STATUS_MANGLER] or telling[STATUS_AVVIK]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(hoved())
