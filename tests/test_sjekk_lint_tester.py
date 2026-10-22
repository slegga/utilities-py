"""Tester for scripts/sjekk-lint-tester.py.

Skriptet lastes inn som en modul slik at hjelpefunksjonene kan testes direkte,
og noen tester kjører hele ``hoved()`` mot fikstur-trær for å sjekke exit-koder
og rapporten.
"""

from __future__ import annotations

import importlib.util
import sys
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


def kjor_hoved(skript: object, monkeypatch: pytest.MonkeyPatch, *argumenter: str) -> int:
    """Kjør hoved() med gitte argumenter og returner exit-koden."""
    monkeypatch.setattr(sys, "argv", ["sjekk-lint-tester.py", *argumenter])
    return skript.hoved()


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


# --- avklarte valg i docstringen ---


def test_docstringen_har_avklarte_valg_ikke_apne_valg(skript: object) -> None:
    """Valgene skal være avklarte beslutninger i teksten, ikke åpne punkter."""
    assert skript.__doc__ is not None
    assert "Avklarte valg" in skript.__doc__
    assert "skal avklares med mennesket" not in skript.__doc__
