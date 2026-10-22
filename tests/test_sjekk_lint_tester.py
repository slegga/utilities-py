"""Tester for scripts/sjekk-lint-tester.py.

Skriptet lastes inn som en modul slik at hjelpefunksjonene kan testes direkte,
og noen tester kjører hele ``hoved()`` mot fikstur-trær for å sjekke exit-koder
og rapporten.

Røyktestene kjører hele skriptet mot syntetiske repo-trær i midlertidige
kataloger (ikke mot de ekte repoene). De bruker den delte fiksturen
``royktre`` (repo-rot med referanser på plass og repoliste), og hver røyktest
går via ``RoykTre.kjor``, som i tillegg kontrollerer at skriptet ikke endrer
noen filer i repo-treet.
"""

from __future__ import annotations

import importlib.util
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

SKRIPTSTI = Path(__file__).resolve().parent.parent / "scripts" / "sjekk-lint-tester.py"


def last_skript() -> object:
    """Last inn scripts/sjekk-lint-tester.py som en modul."""
    spec = importlib.util.spec_from_file_location("sjekk_lint_tester", SKRIPTSTI)
    modul = importlib.util.module_from_spec(spec)
    sys.modules["sjekk_lint_tester"] = modul
    spec.loader.exec_module(modul)
    return modul


@pytest.fixture
def skript() -> object:
    return last_skript()


def skriv(sti: Path, tekst: str) -> Path:
    """Skriv en fil, og lag katalogene som trengs."""
    sti.parent.mkdir(parents=True, exist_ok=True)
    sti.write_text(tekst, encoding="utf-8")
    return sti


def lag_referanser(rot: Path) -> None:
    """Lag referanse-repoene med standard lint-testfiler og ruff.toml."""
    skriv(rot / "utilities-py" / "tests" / "test_lint.py", "REFERANSE-PY\n")
    skriv(rot / "utilities-py" / "ruff.toml", "REFERANSE-RUFF\n")
    skriv(rot / "personlig-py" / "tests" / "lint.rs", "REFERANSE-RS\n")


def lag_python_repo(rot: Path, navn: str) -> Path:
    """Lag et Python-repo som er i tråd med standarden."""
    repo = rot / navn
    skriv(repo / "modul.py", "x = 1\n")
    skriv(repo / "tests" / "test_lint.py", "REFERANSE-PY\n")
    skriv(repo / "ruff.toml", "REFERANSE-RUFF\n")
    return repo


def lag_rust_repo(rot: Path, navn: str) -> Path:
    """Lag et Rust-repo som er i tråd med standarden (lint-test på plass)."""
    repo = rot / navn
    skriv(repo / "Cargo.toml", '[package]\nname = "x"\nversion = "0.1.0"\n')
    skriv(repo / "src" / "lib.rs", "pub fn x() {}\n")
    skriv(repo / "tests" / "lint.rs", "REFERANSE-RS\n")
    return repo


def lag_begge_repo(rot: Path, navn: str) -> Path:
    """Lag et repo med både Python- og Rust-kode, begge lint-testene på plass."""
    repo = lag_python_repo(rot, navn)
    skriv(repo / "Cargo.toml", '[package]\nname = "x"\nversion = "0.1.0"\n')
    skriv(repo / "src" / "lib.rs", "pub fn x() {}\n")
    skriv(repo / "tests" / "lint.rs", "REFERANSE-RS\n")
    return repo


def kjor_hoved(skript: object, monkeypatch: pytest.MonkeyPatch, *argumenter: str) -> int:
    """Kjør hoved() med gitte argumenter og returner exit-koden."""
    monkeypatch.setattr(sys, "argv", ["sjekk-lint-tester.py", *argumenter])
    return skript.hoved()


def les_tre(rot: Path) -> dict[str, bytes]:
    """Les innholdet i alle filene under rot, som {relativ sti: rå bytes}.

    ``read_bytes`` brukes slik at sammenligningen før og etter kjøring dekker
    alt innhold — også binærfiler og rene linjebruddendringer (CRLF mot LF),
    som en tekstlesing med ``read_text`` ville oversett eller kastet feil på.
    """
    return {
        fil.relative_to(rot).as_posix(): fil.read_bytes()
        for fil in sorted(rot.rglob("*"))
        if fil.is_file()
    }


def fiks_kommandoer_fra(ut: str) -> list[str]:
    """Hent fiks-kommandoene fra rapporten, i den rekkefølgen de ble skrevet ut."""
    kommandoer: list[str] = []
    tar_opp = False
    for linje in ut.splitlines():
        if linje.strip() == "Fiks-kommandoer:":
            tar_opp = True
        elif tar_opp and linje.startswith("      "):
            kommandoer.append(linje.strip())
        elif tar_opp:
            tar_opp = False
    return kommandoer


def kjor_fiks_kommandoer(kommandoer: list[str]) -> None:
    """Kjør fiks-kommandoene slik en bruker ville gjort, og krev at de lykkes."""
    for kommando in kommandoer:
        resultat = subprocess.run(kommando, shell=True, capture_output=True, text=True, check=False)
        assert resultat.returncode == 0, (
            f"fiks-kommandoen feilet ({resultat.returncode}): {kommando}\n{resultat.stderr}"
        )


def sjekk_at_ruff_er_standard(repo: Path, referanse: Path) -> None:
    """Slutt-konfigurasjonen for ruff skal være standarden, uten overstyringer."""
    assert (repo / "ruff.toml").read_bytes() == referanse.read_bytes()
    assert not (repo / ".ruff.toml").exists()
    assert "[tool.ruff" not in (repo / "pyproject.toml").read_text(encoding="utf-8")


@dataclass
class RoykTre:
    """Syntetisk repo-tre for røyktestene, med referanser på plass og repoliste."""

    rot: Path
    liste: Path
    skript: object
    capsys: pytest.CaptureFixture
    monkeypatch: pytest.MonkeyPatch

    def sett_repoer(self, *navn: str) -> None:
        """Skriv repo-navnene inn i repolista."""
        skriv(self.liste, "".join(f"{repo}\n" for repo in navn))

    def kjor(self, *navn: str) -> tuple[int, str]:
        """Skriv repolista, kjør hele skriptet mot treet, og kontroller at treet er uendret.

        Skriptet skal bare lese repoene og skrive ut rapporter og fiks-kommandoer
        (avklaring 5) — innholdet i alle filene i repo-treet sammenlignes derfor
        før og etter kjøringen. Returner exit-kode og utskrift slik at testen kan
        sjekke status, fiks-kommandoer og sammendrag.
        """
        self.sett_repoer(*navn)
        foer = les_tre(self.rot)
        kode = kjor_hoved(
            self.skript,
            self.monkeypatch,
            "--repo-rot",
            str(self.rot),
            "--repo-liste",
            str(self.liste),
        )
        ut = self.capsys.readouterr().out
        assert les_tre(self.rot) == foer, "skriptet endret filer i repo-treet"
        return kode, ut


@pytest.fixture
def royktre(
    tmp_path: Path,
    skript: object,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> RoykTre:
    """Delt fikstur for røyktestene: repo-rot med referanser på plass og repoliste."""
    rot = tmp_path / "repoer"
    lag_referanser(rot)
    return RoykTre(
        rot=rot,
        liste=skriv(tmp_path / "repos.txt", ""),
        skript=skript,
        capsys=capsys,
        monkeypatch=monkeypatch,
    )


# --- pytest-oppsett (python_files/testpaths) ---


@pytest.mark.parametrize(
    ("filnavn", "innhold"),
    [
        ("pytest.ini", "[pytest]\ntestpaths = tests\n"),
        ("tox.ini", "[pytest]\ntestpaths = tests\n"),
        ("setup.cfg", "[tool:pytest]\ntestpaths = tests\n"),
    ],
)
def test_uten_python_files_gir_ikke_falskt_avvik(
    skript: object, tmp_path: Path, filnavn: str, innhold: str
) -> None:
    """pytest.ini/tox.ini/setup.cfg uten python_files skal bruke standardmønstrene."""
    repo = tmp_path / "repo"
    skriv(repo / filnavn, innhold)
    testfil = skriv(repo / "tests" / "test_lint.py", "x\n")
    oppsett = skript.les_pytest_oppsett(repo)
    assert oppsett.python_files == skript.STANDARD_PYTHON_FILES
    assert skript.sjekk_pytest_oppdagelse(repo, testfil) is None


def test_tom_python_files_i_pyproject_gir_ikke_falskt_avvik(skript: object, tmp_path: Path) -> None:
    """Tom python_files-liste i pyproject.toml skal også falle tilbake på standarden."""
    repo = tmp_path / "repo"
    skriv(repo / "pyproject.toml", "[tool.pytest.ini_options]\npython_files = []\n")
    testfil = skriv(repo / "tests" / "test_lint.py", "x\n")
    assert skript.sjekk_pytest_oppdagelse(repo, testfil) is None


def test_testpaths_med_prikkeslash_normaliseres(skript: object, tmp_path: Path) -> None:
    """ "./tests" i testpaths skal matche katalogen tests."""
    repo = tmp_path / "repo"
    skriv(repo / "pytest.ini", "[pytest]\ntestpaths = ./tests\n")
    testfil = skriv(repo / "tests" / "test_lint.py", "x\n")
    assert skript.sjekk_pytest_oppdagelse(repo, testfil) is None


def test_python_files_som_ikke_matcher_gir_avvik(skript: object, tmp_path: Path) -> None:
    """python_files som ikke matcher test_lint.py skal gi avvik, ikke stillhet."""
    repo = tmp_path / "repo"
    skriv(repo / "pytest.ini", "[pytest]\npython_files = *_test.py\n")
    testfil = skriv(repo / "tests" / "test_lint.py", "x\n")
    avvik = skript.sjekk_pytest_oppdagelse(repo, testfil)
    assert avvik is not None
    assert "python_files" in avvik


def test_testpaths_som_ikke_dekker_tests_gir_avvik(skript: object, tmp_path: Path) -> None:
    """testpaths som ikke dekker tests/ skal gi avvik, ikke stillhet."""
    repo = tmp_path / "repo"
    skriv(repo / "pytest.ini", "[pytest]\ntestpaths = integration\n")
    testfil = skriv(repo / "tests" / "test_lint.py", "x\n")
    avvik = skript.sjekk_pytest_oppdagelse(repo, testfil)
    assert avvik is not None
    assert "testpaths" in avvik


# --- ruff-konfigurasjon ---


def test_ruff_toml_med_prikk_rapporteres_med_innhold_og_fiks(
    skript: object, tmp_path: Path
) -> None:
    """.ruff.toml overstyrer ruff.toml og skal rapporteres som avvik."""
    repo = tmp_path / "repo"
    referanse = skriv(tmp_path / "referanse.toml", "standard\n")
    skriv(repo / "ruff.toml", "standard\n")
    skriv(repo / ".ruff.toml", "avvikende\n")
    funn = skript.sjekk_python_konfig(repo, referanse)
    assert len(funn) == 1
    assert funn[0].status == skript.STATUS_AVVIK
    assert ".ruff.toml" in funn[0].tekst
    assert "avvikende" in funn[0].tekst
    assert any(kommando.startswith("rm ") and ".ruff.toml" in kommando for kommando in funn[0].fiks)


# --- innholdet i lint-testene ---


def test_avvikende_innhold_i_python_lint_testen_rapporteres(skript: object, tmp_path: Path) -> None:
    """En utradert kopi av test_lint.py skal rapporteres med overskriv-kommando."""
    repo = tmp_path / "repo"
    referanse = skriv(tmp_path / "test_lint.py", "REFERANSE\n")
    skriv(repo / "tests" / "test_lint.py", "print('hallo')\n")
    refs = skript.Referanser(python_test=referanse)
    resultat = skript.Reposultat(navn="repo", sti=repo, klassifisering=skript.KLASSE_PYTHON)
    skript.sjekk_python(repo, refs, resultat)
    avvik = [f for f in resultat.funn if f.status == skript.STATUS_AVVIK]
    assert len(avvik) == 1
    assert "avviker fra" in avvik[0].tekst
    assert any("cp " in kommando and "test_lint.py" in kommando for kommando in avvik[0].fiks)


def test_avvikende_innhold_i_rust_lint_testen_rapporteres(skript: object, tmp_path: Path) -> None:
    """En utradert kopi av lint.rs skal rapporteres med overskriv-kommando."""
    repo = tmp_path / "repo"
    referanse = skriv(tmp_path / "lint.rs", "REFERANSE\n")
    skriv(repo / "tests" / "lint.rs", "fn main() {}\n")
    refs = skript.Referanser(rust_test=referanse)
    resultat = skript.Reposultat(navn="repo", sti=repo, klassifisering=skript.KLASSE_RUST)
    skript.sjekk_rust(repo, refs, resultat)
    avvik = [f for f in resultat.funn if f.status == skript.STATUS_AVVIK]
    assert len(avvik) == 1
    assert "avviker fra" in avvik[0].tekst
    assert any("cp " in kommando and "lint.rs" in kommando for kommando in avvik[0].fiks)


def test_uendret_lint_test_rapporteres_som_ok(skript: object, tmp_path: Path) -> None:
    """En uendret kopi av referansefilen skal ikke gi avvik."""
    repo = tmp_path / "repo"
    referanse = skriv(tmp_path / "test_lint.py", "REFERANSE\n")
    skriv(repo / "tests" / "test_lint.py", "REFERANSE\n")
    refs = skript.Referanser(python_test=referanse)
    resultat = skript.Reposultat(navn="repo", sti=repo, klassifisering=skript.KLASSE_PYTHON)
    skript.sjekk_python(repo, refs, resultat)
    assert resultat.funn == []


# --- Cargo [lints] og autotests ---


def test_lints_seksjoner_rapporteres_med_fullt_innhold(skript: object) -> None:
    """Innstillingene inne i [lints]-seksjonene skal være med i dagens innhold."""
    tekst = (
        '[package]\nname = "x"\n\n'
        "[lints.clippy]\n"
        'all = "warn"\n'
        'dbg_macro = "deny"\n\n'
        "[lints.rust]\n"
        'unsafe_code = "forbid"\n\n'
        "[workspace]\n"
        'lints = { clippy = { all = "warn" } }\n'
    )
    innhold = skript.finn_lints_innhold(tekst)
    assert "[lints.clippy]" in innhold
    assert 'all = "warn"' in innhold
    assert 'dbg_macro = "deny"' in innhold
    assert "[lints.rust]" in innhold
    assert 'unsafe_code = "forbid"' in innhold
    assert 'lints = { clippy = { all = "warn" } }' in innhold
    assert "[package]" not in innhold
    assert "[workspace]" not in innhold


def test_lints_seksjon_rapporteres_i_rust_konfig(skript: object, tmp_path: Path) -> None:
    """Dagens innhold for Cargo [lints] skal ta med innstillingene i seksjonen."""
    repo = tmp_path / "repo"
    skriv(repo / "Cargo.toml", '[package]\nname = "x"\n\n[lints.clippy]\nall = "warn"\n')
    funn = skript.sjekk_rust_konfig(repo)
    assert len(funn) == 1
    assert "[lints.clippy]" in funn[0].tekst
    assert 'all = "warn"' in funn[0].tekst
    assert any(kommando.startswith("python3 ") for kommando in funn[0].fiks)


def test_autotests_false_gir_avvik(skript: object, tmp_path: Path) -> None:
    """autotests = false uten [[test]]-mål betyr at cargo test ikke kjører lint.rs."""
    repo = tmp_path / "crate"
    skriv(repo / "Cargo.toml", '[package]\nname = "x"\nautotests = false\n')
    testfil = skriv(repo / "tests" / "lint.rs", "x\n")
    avvik = skript.sjekk_cargo_oppdagelse(repo, testfil)
    assert avvik is not None
    assert "autotests = false" in avvik


def test_autotests_false_med_eksplisitt_testmal_gir_ikke_avvik(
    skript: object, tmp_path: Path
) -> None:
    """Et [[test]]-mål som peker på lint.rs gjør at cargo test kjører den likevel."""
    repo = tmp_path / "crate"
    skriv(
        repo / "Cargo.toml",
        '[package]\nname = "x"\nautotests = false\n\n[[test]]\nname = "lint"\n',
    )
    testfil = skriv(repo / "tests" / "lint.rs", "x\n")
    assert skript.sjekk_cargo_oppdagelse(repo, testfil) is None


# --- repoliste og ikke-klonede repoer ---


def test_finn_reponavn_ignorerer_vanlige_filer(skript: object, tmp_path: Path) -> None:
    """Filer i repo-rota skal ikke rapporteres som repoer."""
    skriv(tmp_path / "README.md", "x\n")
    skriv(tmp_path / "config.yaml", "x\n")
    (tmp_path / "repo-a").mkdir()
    (tmp_path / ".skjult").mkdir()
    plassering = skript.Plassering(repo_rot=tmp_path)
    assert skript.finn_reponavn(plassering) == ["repo-a"]


def test_ikke_klonet_repo_gir_egen_status_og_exit_0(
    skript: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Repoer som ikke er klonet skal ikke dra exit-koden til 1."""
    rot = tmp_path / "repoer"
    lag_referanser(rot)
    lag_python_repo(rot, "python-repo")
    skriv(tmp_path / "README.md", "løs fil\n")
    liste = skriv(tmp_path / "repos.txt", "python-repo\nmangler-repo\n")
    kode = kjor_hoved(
        skript,
        monkeypatch,
        "--repo-rot",
        str(rot),
        "--repo-liste",
        str(liste),
    )
    ut = capsys.readouterr().out
    assert kode == 0
    assert "python-repo: OK (Python)" in ut
    assert "mangler-repo: ikke klonet (ikke klonet lokalt)" in ut
    assert "1 ikke klonet" in ut


def test_avvik_gir_exit_1_og_fiks_kommandoer(
    skript: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Avvik skal gi exit-kode 1 og konkrete fiks-kommandoer i rapporten."""
    rot = tmp_path / "repoer"
    lag_referanser(rot)
    repo = lag_python_repo(rot, "python-repo")
    skriv(repo / "tests" / "test_lint.py", "print('hallo')\n")
    liste = skriv(tmp_path / "repos.txt", "python-repo\n")
    kode = kjor_hoved(
        skript,
        monkeypatch,
        "--repo-rot",
        str(rot),
        "--repo-liste",
        str(liste),
    )
    ut = capsys.readouterr().out
    assert kode == 1
    assert "python-repo: avvik (Python)" in ut
    assert "Fiks-kommandoer:" in ut
    assert "cp " in ut
    assert "1 avvik" in ut


def test_manglende_referansefiler_gir_exit_2(
    skript: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Uten referansefilene skal skriptet advare og avslutte med exit-kode 2."""
    rot = tmp_path / "repoer"
    lag_python_repo(rot, "python-repo")
    liste = skriv(tmp_path / "repos.txt", "python-repo\n")
    kode = kjor_hoved(
        skript,
        monkeypatch,
        "--repo-rot",
        str(rot),
        "--repo-liste",
        str(liste),
    )
    ut = capsys.readouterr().out
    assert kode == 2
    assert "ADVARSEL" in ut
    assert "python-repo: OK (Python)" in ut
    assert "Ikke kontrollert:" in ut


# --- Røyktester: hele skriptet mot syntetiske repo-trær ---


def test_royktest_repo_uten_kode_gir_intet_a_gjore(royktre: RoykTre) -> None:
    """Et repo uten kode skal rapporteres som «intet å gjøre» og gi exit 0."""
    skriv(royktre.rot / "tomt-repo" / "README.md", "# bare dokumentasjon\n")
    kode, ut = royktre.kjor("tomt-repo")
    assert kode == 0
    assert "tomt-repo: intet å gjøre (ingen kode)" in ut
    assert "Sammendrag: 0 OK, 0 mangler, 0 avvik, 1 intet å gjøre, 0 ikke klonet" in ut


def test_royktest_python_repo_i_orden_gir_ok_og_exit_0(royktre: RoykTre) -> None:
    """Python-repo med lint-test, standard ruff-konfig og lokal testkjøring gir OK og exit 0.

    Pytest-oppsettet i fikstur-repoet er eksplisitt (``pytest.ini`` med
    ``testpaths = tests`` og ``python_files = test_*.py``) og inkluderer
    ``tests/test_lint.py``: den tredje betingelsen — at lint-testen inngår i
    den lokale testkjøringen — skal være demonstrert, ikke bare underforstått
    gjennom pytest sine standardmønstre.
    """
    repo = lag_python_repo(royktre.rot, "python-repo")
    skriv(repo / "pytest.ini", "[pytest]\ntestpaths = tests\npython_files = test_*.py\n")
    kode, ut = royktre.kjor("python-repo")
    assert kode == 0
    assert "python-repo: OK (Python)" in ut
    assert "Sammendrag: 1 OK, 0 mangler, 0 avvik, 0 intet å gjøre, 0 ikke klonet" in ut


def test_royktest_python_repo_uten_lint_test_gir_mangler_og_kopieringskommando(
    royktre: RoykTre,
) -> None:
    """Python-repo uten tests/test_lint.py gir status mangler og kopieringskommando."""
    repo = lag_python_repo(royktre.rot, "python-repo")
    (repo / "tests" / "test_lint.py").unlink()
    kode, ut = royktre.kjor("python-repo")
    assert kode != 0
    assert "python-repo: mangler (Python)" in ut
    assert "tests/test_lint.py finnes ikke" in ut
    assert "Fiks-kommandoer:" in ut
    assert "cp " in ut
    assert str(royktre.rot / "utilities-py" / "tests" / "test_lint.py") in ut
    assert str(repo / "tests" / "test_lint.py") in ut
    assert "Sammendrag: 0 OK, 1 mangler, 0 avvik, 0 intet å gjøre, 0 ikke klonet" in ut


def test_royktest_avvikende_ruff_toml_gir_avvik_med_dagens_innhold_og_fiks(
    royktre: RoykTre,
) -> None:
    """Avvikende ruff.toml gir status avvik, dagens innhold og overskriv-kommando med standarden."""
    repo = lag_python_repo(royktre.rot, "python-repo")
    skriv(repo / "ruff.toml", "line-length = 120\n")
    kode, ut = royktre.kjor("python-repo")
    assert kode != 0
    assert "python-repo: avvik (Python)" in ut
    assert "Dagens innhold" in ut
    assert "line-length = 120" in ut
    assert "Fiks-kommandoer:" in ut
    assert "cp " in ut
    assert str(royktre.rot / "utilities-py" / "ruff.toml") in ut
    assert str(repo / "ruff.toml") in ut
    assert "Sammendrag: 0 OK, 0 mangler, 1 avvik, 0 intet å gjøre, 0 ikke klonet" in ut


def test_royktest_tool_ruff_i_pyproject_gir_avvik_med_dagens_innhold_og_fiks(
    royktre: RoykTre,
) -> None:
    """[tool.ruff] i pyproject.toml gir status avvik, dagens innhold og strip-kommando.

    Fiks-kommandoen er strip-kommandoen som fjerner [tool.ruff]-seksjonene fra
    pyproject.toml (ikke en vilkårlig python3-kommando). Siden ruff.toml
    allerede er standarden i fiksturen, er slutt-konfigurasjonen standarden —
    det verifiseres ved å kjøre fiks-kommandoene og sammenligne med
    referansen i utilities-py.
    """
    repo = lag_python_repo(royktre.rot, "python-repo")
    skriv(repo / "pyproject.toml", "[tool.ruff]\nline-length = 120\n")
    kode, ut = royktre.kjor("python-repo")
    assert kode != 0
    assert "python-repo: avvik (Python)" in ut
    assert "Dagens innhold" in ut
    assert "[tool.ruff]" in ut
    assert "line-length = 120" in ut
    assert "Fiks-kommandoer:" in ut
    assert 'python3 -c "import re,sys,pathlib;' in ut
    assert str(repo / "pyproject.toml") in ut
    assert "Sammendrag: 0 OK, 0 mangler, 1 avvik, 0 intet å gjøre, 0 ikke klonet" in ut
    kjor_fiks_kommandoer(fiks_kommandoer_fra(ut))
    sjekk_at_ruff_er_standard(repo, royktre.rot / "utilities-py" / "ruff.toml")


def test_royktest_tool_ruff_i_pyproject_uten_standard_ruff_toml_skriver_cp_og_strip(
    royktre: RoykTre,
) -> None:
    """[tool.ruff] uten standard ruff.toml gir både cp av standarden og strip av seksjonen.

    Kravet «skriver ut kommandoer som overskriver den med standarden» dekkes
    eksplisitt: kopieringen av ruff.toml fra utilities-py (overskriv med
    standarden) er med i fiks-kommandoene i tillegg til strip av [tool.ruff],
    og slutt-konfigurasjonen etter fiks-kommandoene er standarden.
    """
    repo = lag_python_repo(royktre.rot, "python-repo")
    skriv(repo / "ruff.toml", "line-length = 88\n")
    skriv(repo / "pyproject.toml", "[tool.ruff]\nline-length = 120\n")
    kode, ut = royktre.kjor("python-repo")
    assert kode != 0
    assert "python-repo: avvik (Python)" in ut
    assert "ruff.toml avviker fra standarden" in ut
    assert "[tool.ruff]" in ut
    kilde = royktre.rot / "utilities-py" / "ruff.toml"
    maal = repo / "ruff.toml"
    assert f"cp {shlex.quote(str(kilde))} {shlex.quote(str(maal))}" in ut
    assert 'python3 -c "import re,sys,pathlib;' in ut
    assert str(repo / "pyproject.toml") in ut
    assert "Sammendrag: 0 OK, 0 mangler, 1 avvik, 0 intet å gjøre, 0 ikke klonet" in ut
    kjor_fiks_kommandoer(fiks_kommandoer_fra(ut))
    sjekk_at_ruff_er_standard(repo, kilde)


def test_royktest_testpaths_ikke_samlet_inn_av_pytest_gir_avvik_og_fiks(royktre: RoykTre) -> None:
    """testpaths som ikke dekker tests/ gir status avvik og en fiks som flytter testen.

    Målstien til kopieringen er den første testpath-katalogen — her
    ``integration/test_lint.py`` — altså en testfil som pytest faktisk ville
    samlet inn med dette oppsettet, og den gamle plasseringen fjernes med
    ``rm``.
    """
    repo = lag_python_repo(royktre.rot, "python-repo")
    skriv(repo / "pytest.ini", "[pytest]\ntestpaths = integration\n")
    kode, ut = royktre.kjor("python-repo")
    assert kode != 0
    assert "python-repo: avvik (Python)" in ut
    assert "inngår ikke i den lokale testkjøringen" in ut
    assert "testpaths" in ut
    assert "Fiks-kommandoer:" in ut
    kilde = royktre.rot / "utilities-py" / "tests" / "test_lint.py"
    maal = repo / "integration" / "test_lint.py"
    gammel = repo / "tests" / "test_lint.py"
    assert f"cp {shlex.quote(str(kilde))} {shlex.quote(str(maal))}" in ut
    assert f"rm {shlex.quote(str(gammel))}" in ut
    assert "Sammendrag: 0 OK, 0 mangler, 1 avvik, 0 intet å gjøre, 0 ikke klonet" in ut


def test_royktest_python_files_ikke_samlet_inn_av_pytest_gir_avvik_og_fiks(
    royktre: RoykTre,
) -> None:
    """python_files som ikke matcher test_lint.py gir status avvik og fiks-kommandoer.

    Målstien til kopieringen er ``tests/test_lint.py`` — samme sti som allerede
    finnes, og som ``python_files = *_test.py`` ikke matcher: en no-op som ikke
    løser oppdagelsesavviket. Hva skriptet skal foreslå for dette avviket —
    endring av pytest-oppsettet, eller et mål/filnavn som ``python_files``
    faktisk matcher — er løftet til mennesket og avventer svar.
    """
    repo = lag_python_repo(royktre.rot, "python-repo")
    skriv(repo / "pytest.ini", "[pytest]\npython_files = *_test.py\n")
    kode, ut = royktre.kjor("python-repo")
    assert kode != 0
    assert "python-repo: avvik (Python)" in ut
    assert "inngår ikke i den lokale testkjøringen" in ut
    assert "python_files" in ut
    assert "Fiks-kommandoer:" in ut
    kilde = royktre.rot / "utilities-py" / "tests" / "test_lint.py"
    maal = repo / "tests" / "test_lint.py"
    assert f"cp {shlex.quote(str(kilde))} {shlex.quote(str(maal))}" in ut
    assert "Sammendrag: 0 OK, 0 mangler, 1 avvik, 0 intet å gjøre, 0 ikke klonet" in ut


def test_royktest_rust_repo_i_orden_gir_ok_og_exit_0(royktre: RoykTre) -> None:
    """Rust-repo med tests/lint.rs og standard konfigurasjon gir status OK og exit 0."""
    lag_rust_repo(royktre.rot, "rust-repo")
    kode, ut = royktre.kjor("rust-repo")
    assert kode == 0
    assert "rust-repo: OK (Rust)" in ut
    assert "Sammendrag: 1 OK, 0 mangler, 0 avvik, 0 intet å gjøre, 0 ikke klonet" in ut


def test_royktest_rust_repo_uten_lint_test_gir_mangler_og_kopieringskommando(
    royktre: RoykTre,
) -> None:
    """Rust-repo uten tests/lint.rs gir status mangler og kopieringskommando."""
    repo = lag_rust_repo(royktre.rot, "rust-repo")
    (repo / "tests" / "lint.rs").unlink()
    kode, ut = royktre.kjor("rust-repo")
    assert kode != 0
    assert "rust-repo: mangler (Rust)" in ut
    assert "tests/lint.rs finnes ikke" in ut
    assert "Fiks-kommandoer:" in ut
    assert "cp " in ut
    assert str(royktre.rot / "personlig-py" / "tests" / "lint.rs") in ut
    assert str(repo / "tests" / "lint.rs") in ut
    assert "Sammendrag: 0 OK, 1 mangler, 0 avvik, 0 intet å gjøre, 0 ikke klonet" in ut


def test_royktest_repo_med_python_og_rust_sjekkes_for_begge_deler(royktre: RoykTre) -> None:
    """Repo med både Python og Rust skal sjekkes for begge lint-testene."""
    repo = lag_begge_repo(royktre.rot, "begge-repo")
    (repo / "tests" / "test_lint.py").unlink()
    (repo / "tests" / "lint.rs").unlink()
    kode, ut = royktre.kjor("begge-repo")
    assert kode != 0
    assert "begge-repo: mangler (Python og Rust)" in ut
    assert "tests/test_lint.py finnes ikke" in ut
    assert "tests/lint.rs finnes ikke" in ut
    assert str(royktre.rot / "utilities-py" / "tests" / "test_lint.py") in ut
    assert str(royktre.rot / "personlig-py" / "tests" / "lint.rs") in ut


def test_royktest_alle_repoer_i_orden_gir_exit_0(royktre: RoykTre) -> None:
    """Når alle repoer er OK (eller uten kode) skal skriptet avslutte med exit 0."""
    lag_python_repo(royktre.rot, "python-repo")
    lag_rust_repo(royktre.rot, "rust-repo")
    lag_begge_repo(royktre.rot, "begge-repo")
    skriv(royktre.rot / "tomt-repo" / "README.md", "# bare dokumentasjon\n")
    kode, ut = royktre.kjor("python-repo", "rust-repo", "begge-repo", "tomt-repo")
    assert kode == 0
    assert "python-repo: OK (Python)" in ut
    assert "rust-repo: OK (Rust)" in ut
    assert "begge-repo: OK (Python og Rust)" in ut
    assert "tomt-repo: intet å gjøre (ingen kode)" in ut
    assert "Sammendrag: 3 OK, 0 mangler, 0 avvik, 1 intet å gjøre, 0 ikke klonet" in ut


def test_royktest_blandet_tre_gir_riktig_sammendrag_og_uendret_innhold(royktre: RoykTre) -> None:
    """Blandet tre med alle statusene: sammendraget skal stemme og ingen filer endres.

    ``RoykTre.kjor`` sammenligner innholdet i alle filene i repo-treet før og
    etter kjøringen, også når skriptet finner avvik og skriver ut
    fiks-kommandoer (avklaring 5).
    """
    lag_python_repo(royktre.rot, "python-ok")
    python_mangler = lag_python_repo(royktre.rot, "python-mangler")
    (python_mangler / "tests" / "test_lint.py").unlink()
    python_avvik = lag_python_repo(royktre.rot, "python-avvik")
    skriv(python_avvik / "pyproject.toml", "[tool.ruff]\nline-length = 120\n")
    lag_rust_repo(royktre.rot, "rust-ok")
    rust_mangler = lag_rust_repo(royktre.rot, "rust-mangler")
    (rust_mangler / "tests" / "lint.rs").unlink()
    skriv(royktre.rot / "tomt-repo" / "README.md", "# bare dokumentasjon\n")
    kode, ut = royktre.kjor(
        "python-ok",
        "python-mangler",
        "python-avvik",
        "rust-ok",
        "rust-mangler",
        "tomt-repo",
        "ikke-klonet",
    )
    assert kode != 0
    assert "python-ok: OK (Python)" in ut
    assert "rust-ok: OK (Rust)" in ut
    assert "python-mangler: mangler (Python)" in ut
    assert "rust-mangler: mangler (Rust)" in ut
    assert "python-avvik: avvik (Python)" in ut
    assert "tomt-repo: intet å gjøre (ingen kode)" in ut
    assert "ikke-klonet: ikke klonet (ikke klonet lokalt)" in ut
    assert "Fiks-kommandoer:" in ut
    assert "Sammendrag: 2 OK, 2 mangler, 1 avvik, 1 intet å gjøre, 1 ikke klonet" in ut


# --- avklarte valg i docstringen ---


def test_docstringen_har_avklarte_valg_ikke_apne_valg(skript: object) -> None:
    """Valgene skal være avklarte beslutninger i teksten, ikke åpne punkter."""
    assert skript.__doc__ is not None
    assert "Avklarte valg" in skript.__doc__
    assert "skal avklares med mennesket" not in skript.__doc__
