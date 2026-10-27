"""Tester for scripts/sjekk-lint-tester.py.

Skriptet lastes inn som en modul slik at hjelpefunksjonene kan testes direkte,
og noen tester kjører hele ``hoved()`` mot fikstur-trær for å sjekke exit-koder
og rapporten.

Røyktestene kjører hele skriptet mot syntetiske repo-trær i midlertidige
kataloger (ikke mot de ekte repoene). De bruker den delte fiksturen
``royktre`` (repo-rot med referanser på plass), og hver røyktest går via
``RoykTre.kjor``, som i tillegg kontrollerer at skriptet ikke endrer noen
filer i repo-treet (avklaring 5).
"""

from __future__ import annotations

import importlib.util
import json
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

SKRIPTSTI = Path(__file__).resolve().parent.parent / "scripts" / "sjekk-lint-tester.py"

REFERANSE_HOOK = (
    "#!/bin/sh\n# delbar pre-commit-hook\nruff check .\nruff format --check .\n"
)
REFERANSE_RS = "REFERANSE-RS\n"


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


@pytest.fixture(autouse=True)
def isolert_git_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Hold tester isolert fra global og system git-konfigurasjon.

    ``core.hooksPath`` leses av git på alle nivåer (spec-review punkt 4) —
    uten isolasjon ville tester som krever «ingen hooksPath» feilet på
    maskiner med global hooksPath i dotfiles.
    """
    tom = tmp_path / "tom.gitconfig"
    tom.write_text("", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tom))
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", str(tom))


def sett_global_hooks_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, hooks_path: str
) -> None:
    """Sett core.hooksPath i den isolerte globale git-konfigurasjonen."""
    global_config = tmp_path / "global.gitconfig"
    global_config.write_text(f"[core]\n\thooksPath = {hooks_path}\n", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(global_config))


def skriv(sti: Path, tekst: str) -> Path:
    """Skriv en fil, og lag katalogene som trengs."""
    sti.parent.mkdir(parents=True, exist_ok=True)
    sti.write_text(tekst, encoding="utf-8")
    return sti


def skriv_hook(sti: Path, tekst: str = REFERANSE_HOOK) -> Path:
    """Skriv en pre-commit-hook som er kjørbar (git hopper over ukjørbare hooks)."""
    skriv(sti, tekst)
    sti.chmod(0o755)
    return sti


def lag_git_repo(repo: Path, hooks_path: str | None = "hooks") -> Path:
    """Lag et tomt git-repo, eventuelt med core.hooksPath satt.

    Ekte ``git init`` brukes slik at fiks-kommandoene med ``git config`` kan
    kjøres mot fiksturen, på samme måte som mot de ekte repoene.
    """
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    if hooks_path is not None:
        subprocess.run(
            ["git", "-C", str(repo), "config", "core.hooksPath", hooks_path],
            check=True,
        )
    else:
        subprocess.run(
            ["git", "-C", str(repo), "config", "--unset", "core.hooksPath"],
            check=False,
        )
    return repo


def lag_referanser(rot: Path) -> None:
    """Lag referanse-repoene: pre-commit-hooken (sak #2) og lint.rs (sak #8)."""
    skriv_hook(rot / "utilities-py" / "hooks" / "pre-commit", REFERANSE_HOOK)
    skriv(rot / "personlig-py" / "tests" / "lint.rs", REFERANSE_RS)


def lag_python_repo(
    rot: Path, navn: str, hook: bool = True, hooks_path: str | None = "hooks"
) -> Path:
    """Lag et Python-repo som er i tråd med standarden (pre-commit-hook på plass)."""
    repo = rot / navn
    skriv(repo / "modul.py", "x = 1\n")
    lag_git_repo(repo, hooks_path=hooks_path)
    if hook:
        skriv_hook(repo / "hooks" / "pre-commit", REFERANSE_HOOK)
    return repo


def lag_rust_repo(rot: Path, navn: str) -> Path:
    """Lag et Rust-repo som er i tråd med standarden (lint-test på plass)."""
    repo = rot / navn
    skriv(repo / "Cargo.toml", '[package]\nname = "x"\nversion = "0.1.0"\n')
    skriv(repo / "src" / "lib.rs", "pub fn x() {}\n")
    skriv(repo / "tests" / "lint.rs", REFERANSE_RS)
    return repo


def lag_begge_repo(rot: Path, navn: str) -> Path:
    """Lag et repo med både Python- og Rust-kode, med hook og lint-test på plass."""
    repo = lag_python_repo(rot, navn)
    skriv(repo / "Cargo.toml", '[package]\nname = "x"\nversion = "0.1.0"\n')
    skriv(repo / "src" / "lib.rs", "pub fn x() {}\n")
    skriv(repo / "tests" / "lint.rs", REFERANSE_RS)
    return repo


def sammendrag(ok: int = 0, mangler: int = 0, avvik: int = 0, intet: int = 0) -> str:
    """Forventet sammendragslinje for røyktestene.

    Referanse-repoene i fiksturen oppdages også og teller med:
    ``personlig-py`` (Rust-referansen) gir 1 OK, og ``utilities-py`` (bare
    hook-referansen, ingen kode) gir 1 «intet å gjøre».
    """
    return f"Sammendrag: {ok + 1} OK, {mangler} mangler, {avvik} avvik, {intet + 1} intet å gjøre"


def kjor_hoved(
    skript: object, monkeypatch: pytest.MonkeyPatch, *argumenter: str
) -> int:
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
    """Kjør fiks-kommandoene slik en bruker ville gjort, og krev at de lykkes.

    Ledende ``python3`` byttes ut med tolken testene kjører under
    (``sys.executable``): testene skal ikke avhenge av hva ``python3`` peker
    på i PATH — under ``uv run pytest`` er det uvs tolk som gjelder, ikke en
    eventuell ``~/.venv``.
    """
    for kommando in kommandoer:
        if kommando.startswith("python3 "):
            kommando = shlex.quote(sys.executable) + kommando[len("python3") :]
        resultat = subprocess.run(
            kommando, shell=True, capture_output=True, text=True, check=False
        )
        assert resultat.returncode == 0, (
            f"fiks-kommandoen feilet ({resultat.returncode}): {kommando}\n{resultat.stderr}"
        )


@dataclass
class RoykTre:
    """Syntetisk repo-tre for røyktestene, med referanser på plass."""

    rot: Path
    skript: object
    capsys: pytest.CaptureFixture
    monkeypatch: pytest.MonkeyPatch

    def kjor(self) -> tuple[int, str]:
        """Kjør hele skriptet mot treet, og kontroller at treet er uendret.

        Skriptet skal bare lese repoene og skrive ut rapporter og fiks-kommandoer
        (avklaring 5) — innholdet i alle filene i repo-treet sammenlignes derfor
        før og etter kjøringen. Returner exit-kode og utskrift slik at testen kan
        sjekke status, fiks-kommandoer og sammendrag. Repoene er alle
        underkataloger under rot (menneskevedtak i utilities-py#11) — det finnes
        ingen repoliste.
        """
        foer = les_tre(self.rot)
        kode = kjor_hoved(self.skript, self.monkeypatch, "--repo-rot", str(self.rot))
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
    """Delt fikstur for røyktestene: repo-rot med referanser på plass."""
    rot = tmp_path / "repoer"
    rot.mkdir()
    lag_referanser(rot)
    return RoykTre(rot=rot, skript=skript, capsys=capsys, monkeypatch=monkeypatch)


# --- repo-oppdagelse (ett nivå av kataloger under meta-privat) ---


def test_finn_reponavn_tar_bare_underkataloger(skript: object, tmp_path: Path) -> None:
    """Filer, skjulte kataloger og byggeartefakter skal ikke rapporteres som repoer."""
    skriv(tmp_path / "README.md", "x\n")
    (tmp_path / "repo-a").mkdir()
    (tmp_path / ".skjult").mkdir()
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / ".venv").mkdir()
    assert skript.finn_reponavn(tmp_path) == ["repo-a"]


def test_repoer_er_underkataloger_uten_repoliste(
    skript: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    """Uten argumenter brukes alle underkataloger under repo-rota — ingen repo-liste."""
    rot = tmp_path / "repoer"
    lag_referanser(rot)
    lag_python_repo(rot, "b-repo")
    lag_python_repo(rot, "a-repo")
    kode = kjor_hoved(skript, monkeypatch, "--repo-rot", str(rot))
    ut = capsys.readouterr().out
    assert kode == 0
    assert "Repoliste: alle underkataloger ett nivå under repo-rota" in ut
    assert ut.index("a-repo:") < ut.index("b-repo:")


# --- pre-commit-hook for Python ---


def test_precommit_mangler_gir_mangler_og_installeringskommando(
    skript: object, tmp_path: Path
) -> None:
    """Uten pre-commit-hook skal statusen være mangler, med kopiering og aktivering."""
    repo = lag_python_repo(tmp_path, "repo", hook=False)
    referanse = skriv_hook(tmp_path / "utilities-py" / "hooks" / "pre-commit")
    refs = skript.Referanser(python_hook=referanse)
    resultat = skript.Reposultat(
        navn="repo", sti=repo, klassifisering=skript.KLASSE_PYTHON
    )
    skript.sjekk_python(repo, skript.finn_git_rot(repo), refs, resultat)
    assert resultat.status == skript.STATUS_MANGLER
    assert "Pre-commit-hooken mangler" in resultat.funn[0].tekst
    assert any(
        "cp " in kommando and "pre-commit" in kommando
        for kommando in resultat.funn[0].fiks
    )
    assert any(
        "git " in kommando and "core.hooksPath" in kommando
        for kommando in resultat.funn[0].fiks
    )


def test_uten_git_repo_gir_mangler_uten_fiks_kommandoer(
    skript: object, tmp_path: Path
) -> None:
    """Katalog som ikke ligger i noe git-repo kan ikke ha pre-commit-hook — ingen farlige fiks."""
    repo = tmp_path / "repo"
    skriv(repo / "modul.py", "x = 1\n")
    resultat = skript.Reposultat(
        navn="repo", sti=repo, klassifisering=skript.KLASSE_PYTHON
    )
    skript.sjekk_python(repo, skript.finn_git_rot(repo), skript.Referanser(), resultat)
    assert resultat.status == skript.STATUS_MANGLER
    assert "ikke i noe git-repo" in resultat.funn[0].tekst
    assert resultat.funn[0].fiks == []


def test_precommit_ikke_aktivert_gir_avvik(skript: object, tmp_path: Path) -> None:
    """Hook-fil som ligger i hooks/ uten å være aktivert gir avvik, ikke stillhet."""
    repo = lag_python_repo(tmp_path, "repo", hook=False, hooks_path=None)
    skriv_hook(repo / "hooks" / "pre-commit", REFERANSE_HOOK)
    referanse = skriv_hook(tmp_path / "utilities-py" / "hooks" / "pre-commit")
    refs = skript.Referanser(python_hook=referanse)
    resultat = skript.Reposultat(
        navn="repo", sti=repo, klassifisering=skript.KLASSE_PYTHON
    )
    skript.sjekk_python(repo, skript.finn_git_rot(repo), refs, resultat)
    assert resultat.status == skript.STATUS_AVVIK
    assert "er ikke aktivert" in resultat.funn[0].tekst
    assert any("core.hooksPath" in kommando for kommando in resultat.funn[0].fiks)


def test_global_core_hooks_path_med_hook_gir_ikke_funn(
    skript: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Globalt aktivert core.hooksPath (f.eks. fra dotfiles) skal telle som aktivert.

    Spec-review punkt 4: git kjører hooken fra global sti også for dette
    repoet — rapporten må ikke si «mangler»/«ikke aktivert» da.
    """
    repo = lag_python_repo(tmp_path, "repo", hook=False, hooks_path=None)
    global_hooks = tmp_path / "dotfiles" / "hooks"
    skriv_hook(global_hooks / "pre-commit", REFERANSE_HOOK)
    sett_global_hooks_path(tmp_path, monkeypatch, str(global_hooks))
    referanse = skriv_hook(tmp_path / "utilities-py" / "hooks" / "pre-commit")
    refs = skript.Referanser(python_hook=referanse)
    resultat = skript.Reposultat(
        navn="repo", sti=repo, klassifisering=skript.KLASSE_PYTHON
    )
    skript.sjekk_python(repo, skript.finn_git_rot(repo), refs, resultat)
    assert resultat.funn == []
    assert skript.finn_aktiv_hook(repo) == global_hooks / "pre-commit"


def test_global_core_hooks_path_uten_hook_gir_fortsatt_ikke_aktivert(
    skript: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Når global core.hooksPath peker utenfor repoet, kjører git ikke hooks/pre-commit der."""
    repo = lag_python_repo(tmp_path, "repo", hook=False, hooks_path=None)
    skriv_hook(repo / "hooks" / "pre-commit", REFERANSE_HOOK)
    tom_hooks = tmp_path / "dotfiles" / "hooks"
    tom_hooks.mkdir(parents=True)
    sett_global_hooks_path(tmp_path, monkeypatch, str(tom_hooks))
    referanse = skriv_hook(tmp_path / "utilities-py" / "hooks" / "pre-commit")
    refs = skript.Referanser(python_hook=referanse)
    resultat = skript.Reposultat(
        navn="repo", sti=repo, klassifisering=skript.KLASSE_PYTHON
    )
    skript.sjekk_python(repo, skript.finn_git_rot(repo), refs, resultat)
    assert any("er ikke aktivert" in f.tekst for f in resultat.funn)
    assert skript.finn_aktiv_hook(repo) is None


def test_precommit_ikke_aktivert_uten_ruff_rapporterer_innhold_og_overskriving(
    skript: object, tmp_path: Path
) -> None:
    """Innholdet i en inaktiv hook vurderes mot referansen — ikke bare aktiveres.

    Verifisert med en markdownlint-hook, slik ``dokumentasjon`` har i dag:
    hooken kjører ikke Python-linting, og skal overskrives med referansekopien
    (avklaring 4), ikke aktiveres som den er.
    """
    repo = lag_python_repo(tmp_path, "repo", hook=False, hooks_path=None)
    skriv_hook(repo / "hooks" / "pre-commit", "#!/bin/sh\nmarkdownlint\n")
    referanse = skriv_hook(tmp_path / "utilities-py" / "hooks" / "pre-commit")
    refs = skript.Referanser(python_hook=referanse)
    resultat = skript.Reposultat(
        navn="repo", sti=repo, klassifisering=skript.KLASSE_PYTHON
    )
    skript.sjekk_python(repo, skript.finn_git_rot(repo), refs, resultat)
    assert resultat.status == skript.STATUS_AVVIK
    assert any("er ikke aktivert" in f.tekst for f in resultat.funn)
    assert any("kjører ikke ruff" in f.tekst for f in resultat.funn)
    assert any("Dagens innhold" in f.tekst for f in resultat.funn)
    assert any("markdownlint" in f.tekst for f in resultat.funn)
    assert any("cp " in kommando for f in resultat.funn for kommando in f.fiks)


def test_precommit_ikke_aktivert_med_utradert_innhold_rapporterer_overskriving(
    skript: object, tmp_path: Path
) -> None:
    """En inaktiv, utradert hook skal også vurderes mot referansen (avklaring 4)."""
    repo = lag_python_repo(tmp_path, "repo", hook=False, hooks_path=None)
    skriv_hook(repo / "hooks" / "pre-commit", "#!/bin/sh\nruff check .\n# endret\n")
    referanse = skriv_hook(tmp_path / "utilities-py" / "hooks" / "pre-commit")
    refs = skript.Referanser(python_hook=referanse)
    resultat = skript.Reposultat(
        navn="repo", sti=repo, klassifisering=skript.KLASSE_PYTHON
    )
    skript.sjekk_python(repo, skript.finn_git_rot(repo), refs, resultat)
    assert resultat.status == skript.STATUS_AVVIK
    assert any("er ikke aktivert" in f.tekst for f in resultat.funn)
    assert any("avviker fra referansen" in f.tekst for f in resultat.funn)
    assert any("cp " in kommando for f in resultat.funn for kommando in f.fiks)


def test_precommit_ikke_kjoerbar_gir_avvik(skript: object, tmp_path: Path) -> None:
    """En hook uten execute-bit blir hoppet over av git, og skal rapporteres."""
    repo = lag_python_repo(tmp_path, "repo", hook=False)
    skriv(repo / "hooks" / "pre-commit", REFERANSE_HOOK)
    referanse = skriv_hook(tmp_path / "utilities-py" / "hooks" / "pre-commit")
    refs = skript.Referanser(python_hook=referanse)
    resultat = skript.Reposultat(
        navn="repo", sti=repo, klassifisering=skript.KLASSE_PYTHON
    )
    skript.sjekk_python(repo, skript.finn_git_rot(repo), refs, resultat)
    avvik = [f for f in resultat.funn if f.status == skript.STATUS_AVVIK]
    assert any("er ikke kjørbar" in f.tekst for f in avvik)
    assert any(kommando.startswith("chmod +x") for kommando in avvik[0].fiks)


def test_precommit_uten_ruff_gir_avvik(skript: object, tmp_path: Path) -> None:
    """En aktiv hook som ikke kjører ruff dekker ikke Python-lintingen."""
    repo = lag_python_repo(tmp_path, "repo", hook=False)
    skriv_hook(repo / "hooks" / "pre-commit", "#!/bin/sh\nmarkdownlint\n")
    referanse = skriv_hook(tmp_path / "utilities-py" / "hooks" / "pre-commit")
    refs = skript.Referanser(python_hook=referanse)
    resultat = skript.Reposultat(
        navn="repo", sti=repo, klassifisering=skript.KLASSE_PYTHON
    )
    skript.sjekk_python(repo, skript.finn_git_rot(repo), refs, resultat)
    assert resultat.status == skript.STATUS_AVVIK
    assert any("kjører ikke ruff" in f.tekst for f in resultat.funn)
    assert any("cp " in kommando for f in resultat.funn for kommando in f.fiks)


def test_precommit_avvikende_innhold_gir_avvik_og_kopieringskommando(
    skript: object, tmp_path: Path
) -> None:
    """En utradert kopi av hooken skal rapporteres med overskriv-kommando (avklaring 4)."""
    repo = lag_python_repo(tmp_path, "repo", hook=False)
    skriv_hook(repo / "hooks" / "pre-commit", "#!/bin/sh\nruff check .\n# endret\n")
    referanse = skriv_hook(tmp_path / "utilities-py" / "hooks" / "pre-commit")
    refs = skript.Referanser(python_hook=referanse)
    resultat = skript.Reposultat(
        navn="repo", sti=repo, klassifisering=skript.KLASSE_PYTHON
    )
    skript.sjekk_python(repo, skript.finn_git_rot(repo), refs, resultat)
    avvik = [f for f in resultat.funn if f.status == skript.STATUS_AVVIK]
    assert len(avvik) == 1
    assert "avviker fra referansen" in avvik[0].tekst
    assert "Dagens innhold" in avvik[0].tekst
    assert any(
        "cp " in kommando and "pre-commit" in kommando for kommando in avvik[0].fiks
    )


def test_precommit_paa_plass_gir_ikke_funn(skript: object, tmp_path: Path) -> None:
    """Aktiv hook som er referansefilen kopiert uendret skal ikke gi funn."""
    repo = lag_python_repo(tmp_path, "repo")
    referanse = skriv_hook(tmp_path / "utilities-py" / "hooks" / "pre-commit")
    refs = skript.Referanser(python_hook=referanse)
    resultat = skript.Reposultat(
        navn="repo", sti=repo, klassifisering=skript.KLASSE_PYTHON
    )
    skript.sjekk_python(repo, skript.finn_git_rot(repo), refs, resultat)
    assert resultat.funn == []


def test_gammel_lint_test_gir_avvik_og_rm(skript: object, tmp_path: Path) -> None:
    """tests/test_lint.py er gammel leveranseform — linting skal ikke skje i pytest."""
    repo = lag_python_repo(tmp_path, "repo")
    skriv(repo / "tests" / "test_lint.py", "print('lint')\n")
    referanse = skriv_hook(tmp_path / "utilities-py" / "hooks" / "pre-commit")
    refs = skript.Referanser(python_hook=referanse)
    resultat = skript.Reposultat(
        navn="repo", sti=repo, klassifisering=skript.KLASSE_PYTHON
    )
    skript.sjekk_python(repo, skript.finn_git_rot(repo), refs, resultat)
    avvik = [f for f in resultat.funn if f.status == skript.STATUS_AVVIK]
    assert any("gammel leveranseform" in f.tekst for f in avvik)
    assert any(
        kommando.startswith("rm ") and "test_lint.py" in kommando
        for f in avvik
        for kommando in f.fiks
    )


# --- ruff-konfigurasjon og E501-unntaket ---


def test_ruff_oppsett_med_kun_e501_unntak_gir_ikke_avvik(
    skript: object, tmp_path: Path
) -> None:
    """Standarden er ruff default, med E501-unntaket som eneste tillatte innstilling."""
    repo = tmp_path / "repo"
    skriv(repo / "pyproject.toml", '[tool.ruff.lint]\nignore = ["E501"]\n')
    assert skript.sjekk_python_konfig(repo) == []
    skriv(repo / "ruff.toml", '[lint]\nignore = ["E501"]\n')
    (repo / "pyproject.toml").unlink()
    assert skript.sjekk_python_konfig(repo) == []


def test_tool_ruff_med_e501_unntak_bevarer_unntaket_ved_fiks(
    skript: object, tmp_path: Path
) -> None:
    """«Ignore E501 skal videre føres overalt»: fiks-kommandoen bevarer E501-unntaket."""
    repo = tmp_path / "repo"
    skriv(
        repo / "pyproject.toml",
        "[tool.ruff]\nline-length = 79\n\n"
        '[tool.ruff.lint]\nselect = ["E", "F"]\nignore = ["E501"]\n',
    )
    funn = skript.sjekk_python_konfig(repo)
    assert len(funn) == 1
    assert funn[0].status == skript.STATUS_AVVIK
    assert any(kommando.startswith("python3 ") for kommando in funn[0].fiks)
    kjor_fiks_kommandoer(funn[0].fiks)
    tekst = (repo / "pyproject.toml").read_text(encoding="utf-8")
    assert 'ignore = ["E501"]' in tekst
    assert "line-length" not in tekst
    assert "select" not in tekst
    assert skript.sjekk_python_konfig(repo) == []


def test_tool_ruff_uten_e501_unntak_fjernes_ved_fiks(
    skript: object, tmp_path: Path
) -> None:
    """Uten E501-unntak fjernes [tool.ruff] helt — ruff default gjelder."""
    repo = tmp_path / "repo"
    skriv(
        repo / "pyproject.toml",
        "[tool.ruff]\nline-length = 100\n\n[tool.ruff.format]\nx = 1\n",
    )
    funn = skript.sjekk_python_konfig(repo)
    assert len(funn) == 1
    kjor_fiks_kommandoer(funn[0].fiks)
    tekst = (repo / "pyproject.toml").read_text(encoding="utf-8")
    assert "[tool.ruff" not in tekst
    assert skript.sjekk_python_konfig(repo) == []


def test_ruff_toml_fjernes_ved_fiks_uten_unntak(skript: object, tmp_path: Path) -> None:
    """Gammel ruff.toml uten E501-unntak fjernes, slik at default gjelder."""
    repo = tmp_path / "repo"
    skriv(repo / "ruff.toml", 'line-length = 100\n[lint]\nselect = ["E", "F"]\n')
    funn = skript.sjekk_python_konfig(repo)
    assert len(funn) == 1
    assert "ruff.toml avviker" in funn[0].tekst
    kjor_fiks_kommandoer(funn[0].fiks)
    assert not (repo / "ruff.toml").exists()
    assert skript.sjekk_python_konfig(repo) == []


def test_ruff_toml_med_e501_unntak_skrives_om_ikke_fjernes(
    skript: object, tmp_path: Path
) -> None:
    """E501-unntaket i ruff.toml bevares — filen skrives om til kun unntaket."""
    repo = tmp_path / "repo"
    skriv(
        repo / "ruff.toml",
        'line-length = 100\n[lint]\nignore = ["E501"]\nselect = ["E"]\n',
    )
    funn = skript.sjekk_python_konfig(repo)
    assert len(funn) == 1
    kjor_fiks_kommandoer(funn[0].fiks)
    assert (repo / "ruff.toml").read_text(
        encoding="utf-8"
    ) == '[lint]\nignore = ["E501"]\n'
    assert skript.sjekk_python_konfig(repo) == []


def test_ruff_toml_og_tool_ruff_samtidig_gir_avvik(
    skript: object, tmp_path: Path
) -> None:
    """To ruff-konfigurasjoner kjemper om hvilken som gjelder — fiks fjerner den ene."""
    repo = tmp_path / "repo"
    ruff_toml = skriv(repo / "ruff.toml", '[lint]\nignore = ["E501"]\n')
    skriv(repo / "pyproject.toml", '[tool.ruff.lint]\nignore = ["E501"]\n')
    funn = skript.sjekk_python_konfig(repo)
    assert len(funn) == 1
    assert "kjemper om hvilken som gjelder" in funn[0].tekst
    assert "Behold ruff.toml" in funn[0].tekst, (
        "rapporten skal navngi kilden som beholdes, ikke bare si «Behold én»"
    )
    assert funn[0].fiks, (
        "avviket må ha fiks-kommandoer som fjerner den overskytende kilden"
    )
    assert any("pyproject.toml" in kommando for kommando in funn[0].fiks)
    kjor_fiks_kommandoer(funn[0].fiks)
    assert ruff_toml.exists()
    assert skript.sjekk_python_konfig(repo) == []


def test_flere_ruff_konfigurasjoner_med_avvik_fikses_helt(
    skript: object, tmp_path: Path
) -> None:
    """Når én av to konkurrerende konfigurasjoner fikses, må den andre fjernes også.

    Ellers ville avviket «Flere ruff-konfigurasjoner» stått igjen ved neste
    kjøring (spesifikasjonens pkt. 4: fiks-kommandoene skal fikse avviket).
    """
    repo = tmp_path / "repo"
    skriv(
        repo / "ruff.toml",
        'line-length = 100\n[lint]\nselect = ["E"]\nignore = ["E501"]\n',
    )
    skriv(repo / "pyproject.toml", "[tool.ruff]\nline-length = 79\n")
    funn = skript.sjekk_python_konfig(repo)
    assert len(funn) == 1
    assert "kjemper om hvilken som gjelder" in funn[0].tekst
    assert len(funn[0].fiks) == 2
    kjor_fiks_kommandoer(funn[0].fiks)
    assert skript.sjekk_python_konfig(repo) == []


# --- Cargo [lints], autotests og Rust ---


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


def test_lints_seksjon_rapporteres_i_rust_konfig(
    skript: object, tmp_path: Path
) -> None:
    """Dagens innhold for Cargo [lints] skal ta med innstillingene i seksjonen."""
    repo = tmp_path / "repo"
    skriv(
        repo / "Cargo.toml", '[package]\nname = "x"\n\n[lints.clippy]\nall = "warn"\n'
    )
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


def test_avvikende_innhold_i_rust_lint_testen_rapporteres(
    skript: object, tmp_path: Path
) -> None:
    """En utradert kopi av lint.rs skal rapporteres med overskriv-kommando."""
    repo = tmp_path / "repo"
    referanse = skriv(tmp_path / "lint.rs", "REFERANSE\n")
    skriv(repo / "tests" / "lint.rs", "fn main() {}\n")
    refs = skript.Referanser(rust_test=referanse)
    resultat = skript.Reposultat(
        navn="repo", sti=repo, klassifisering=skript.KLASSE_RUST
    )
    skript.sjekk_rust(repo, refs, resultat)
    avvik = [f for f in resultat.funn if f.status == skript.STATUS_AVVIK]
    assert len(avvik) == 1
    assert "avviker fra" in avvik[0].tekst
    assert any(
        "cp " in kommando and "lint.rs" in kommando for kommando in avvik[0].fiks
    )


# --- referanser og exit-koder ---


def test_avvik_gir_exit_1_og_fiks_kommandoer(
    skript: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    """Avvik skal gi exit-kode 1 og konkrete fiks-kommandoer i rapporten."""
    rot = tmp_path / "repoer"
    rot.mkdir()
    lag_referanser(rot)
    repo = lag_python_repo(rot, "python-repo", hook=False)
    skriv_hook(repo / "hooks" / "pre-commit", "#!/bin/sh\nruff check .\n# endret\n")
    kode = kjor_hoved(skript, monkeypatch, "--repo-rot", str(rot))
    ut = capsys.readouterr().out
    assert kode == 1
    assert "python-repo: avvik (Python)" in ut
    assert "Fiks-kommandoer:" in ut
    assert "cp " in ut
    assert "1 avvik" in ut


def test_manglende_referansefiler_gir_exit_2(
    skript: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    """Uten referansefilene, og uten reelle avvik, blir det exit-kode 2."""
    rot = tmp_path / "repoer"
    lag_python_repo(rot, "python-repo")
    kode = kjor_hoved(skript, monkeypatch, "--repo-rot", str(rot))
    ut = capsys.readouterr().out
    assert kode == 2
    assert "ADVARSEL" in ut
    assert "python-repo: OK (Python)" in ut
    assert "Ikke kontrollert:" in ut


def test_reelle_avvik_vinner_over_manglende_referanse(
    skript: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    """Reelle avvik gir exit 1 selv når referansefilene mangler.

    Exit-kode 2 skal ikke maskere avvik som faktisk er funnet (avklart
    2026-10-24: exit 1 vinner over exit 2).
    """
    rot = tmp_path / "repoer"
    lag_python_repo(rot, "python-repo", hook=False)
    kode = kjor_hoved(skript, monkeypatch, "--repo-rot", str(rot))
    ut = capsys.readouterr().out
    assert kode == 1
    assert "ADVARSEL" in ut
    assert "python-repo: mangler (Python)" in ut
    assert "1 mangler" in ut


def test_json_rapport_er_maskinlesbar(
    skript: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    """--json gir rapporten som ett maskinlesbart JSON-dokument for kontroller."""
    rot = tmp_path / "repoer"
    rot.mkdir()
    lag_referanser(rot)
    lag_python_repo(rot, "python-repo", hook=False)
    kode = kjor_hoved(skript, monkeypatch, "--repo-rot", str(rot), "--json")
    data = json.loads(capsys.readouterr().out)
    assert kode == 1
    assert data["exit_kode"] == 1
    assert data["sammendrag"] == {"OK": 1, "mangler": 1, "avvik": 0, "intet å gjøre": 1}
    assert data["referanser"]["mangler"] == []
    assert data["repo_rot"] == str(rot)
    python = next(repo for repo in data["repoer"] if repo["navn"] == "python-repo")
    assert python["status"] == "mangler"
    assert python["klassifisering"] == "python"
    assert any("cp " in k for funn in python["funn"] for k in funn["fiks"])


# --- Røyktester: hele skriptet mot syntetiske repo-trær ---


def test_royktest_repo_uten_kode_gir_intet_a_gjore(royktre: RoykTre) -> None:
    """Et repo uten kode skal rapporteres som «intet å gjøre» og gi exit 0."""
    skriv(royktre.rot / "tomt-repo" / "README.md", "# bare dokumentasjon\n")
    kode, ut = royktre.kjor()
    assert kode == 0
    assert "tomt-repo: intet å gjøre (ingen kode)" in ut
    assert sammendrag(ok=0, intet=1) in ut


def test_royktest_python_repo_i_orden_gir_ok_og_exit_0(royktre: RoykTre) -> None:
    """Python-repo med aktiv pre-commit-hook som er referansekopien gir OK og exit 0."""
    lag_python_repo(royktre.rot, "python-repo")
    kode, ut = royktre.kjor()
    assert kode == 0
    assert "python-repo: OK (Python)" in ut
    assert sammendrag(ok=1) in ut


def test_royktest_python_repo_uten_hook_gir_mangler_og_installeringskommando(
    royktre: RoykTre,
) -> None:
    """Python-repo uten pre-commit-hook gir status mangler og kommando som installerer hooken."""
    repo = lag_python_repo(royktre.rot, "python-repo", hook=False)
    kode, ut = royktre.kjor()
    assert kode != 0
    assert "python-repo: mangler (Python)" in ut
    assert "Pre-commit-hooken mangler" in ut
    assert "Fiks-kommandoer:" in ut
    kilde = royktre.rot / "utilities-py" / "hooks" / "pre-commit"
    maal = repo / "hooks" / "pre-commit"
    assert f"cp {shlex.quote(str(kilde))} {shlex.quote(str(maal))}" in ut
    assert "core.hooksPath hooks" in ut
    assert sammendrag(mangler=1) in ut
    kjor_fiks_kommandoer(fiks_kommandoer_fra(ut))
    assert maal.read_text(encoding="utf-8") == REFERANSE_HOOK


def test_royktest_gammel_lint_test_gir_avvik_og_fjernes(royktre: RoykTre) -> None:
    """Gammel lint-test i pytest rapporteres som avvik, og fiks fjerner den."""
    repo = lag_python_repo(royktre.rot, "python-repo")
    gammel = skriv(repo / "tests" / "test_lint.py", "print('lint')\n")
    kode, ut = royktre.kjor()
    assert kode == 1
    assert "python-repo: avvik (Python)" in ut
    assert "gammel leveranseform" in ut
    assert sammendrag(avvik=1) in ut
    kjor_fiks_kommandoer(fiks_kommandoer_fra(ut))
    assert not gammel.exists()


def test_royktest_tool_ruff_med_e501_unntak_gir_avvik_og_fiks_bevarer_unntaket(
    royktre: RoykTre,
) -> None:
    """[tool.ruff] rapporteres med dagens innhold, og fiks bevarer E501-unntaket."""
    repo = lag_python_repo(royktre.rot, "python-repo")
    skriv(
        repo / "pyproject.toml",
        '[tool.ruff]\nline-length = 79\n\n[tool.ruff.lint]\nignore = ["E501"]\n',
    )
    kode, ut = royktre.kjor()
    assert kode == 1
    assert "python-repo: avvik (Python)" in ut
    assert "Dagens innhold" in ut
    assert "[tool.ruff]" in ut
    assert "line-length = 79" in ut
    assert sammendrag(avvik=1) in ut
    kjor_fiks_kommandoer(fiks_kommandoer_fra(ut))
    tekst = (repo / "pyproject.toml").read_text(encoding="utf-8")
    assert 'ignore = ["E501"]' in tekst
    assert "line-length" not in tekst
    assert "select" not in tekst


def test_royktest_avvikende_ruff_toml_gir_avvik_og_fjernes(royktre: RoykTre) -> None:
    """Avvikende ruff.toml gir status avvik, dagens innhold og fiks som fjerner filen."""
    repo = lag_python_repo(royktre.rot, "python-repo")
    ruff_toml = skriv(repo / "ruff.toml", "line-length = 120\n")
    kode, ut = royktre.kjor()
    assert kode == 1
    assert "python-repo: avvik (Python)" in ut
    assert "Dagens innhold" in ut
    assert "line-length = 120" in ut
    assert sammendrag(avvik=1) in ut
    kjor_fiks_kommandoer(fiks_kommandoer_fra(ut))
    assert not ruff_toml.exists()


def test_royktest_rust_repo_i_orden_gir_ok_og_exit_0(royktre: RoykTre) -> None:
    """Rust-repo med tests/lint.rs og standard konfigurasjon gir status OK og exit 0."""
    lag_rust_repo(royktre.rot, "rust-repo")
    kode, ut = royktre.kjor()
    assert kode == 0
    assert "rust-repo: OK (Rust)" in ut
    assert sammendrag(ok=1) in ut


def test_royktest_rust_repo_uten_lint_test_gir_mangler_og_kopieringskommando(
    royktre: RoykTre,
) -> None:
    """Rust-repo uten tests/lint.rs gir status mangler og kopieringskommando."""
    repo = lag_rust_repo(royktre.rot, "rust-repo")
    (repo / "tests" / "lint.rs").unlink()
    kode, ut = royktre.kjor()
    assert kode != 0
    assert "rust-repo: mangler (Rust)" in ut
    assert "tests/lint.rs finnes ikke" in ut
    assert "Fiks-kommandoer:" in ut
    assert (
        f"cp {shlex.quote(str(royktre.rot / 'personlig-py' / 'tests' / 'lint.rs'))}"
        in ut
    )
    assert sammendrag(mangler=1) in ut


def test_royktest_repo_med_python_og_rust_sjekkes_for_begge_deler(
    royktre: RoykTre,
) -> None:
    """Repo med både Python og Rust skal sjekkes for både hook og lint-test."""
    repo = lag_begge_repo(royktre.rot, "begge-repo")
    (repo / "hooks" / "pre-commit").unlink()
    (repo / "tests" / "lint.rs").unlink()
    kode, ut = royktre.kjor()
    assert kode != 0
    assert "begge-repo: mangler (Python og Rust)" in ut
    assert "Pre-commit-hooken mangler" in ut
    assert "tests/lint.rs finnes ikke" in ut
    assert "pre-commit" in ut
    assert "lint.rs" in ut


def test_royktest_alle_repoer_i_orden_gir_exit_0(royktre: RoykTre) -> None:
    """Når alle repoer er OK (eller uten kode) skal skriptet avslutte med exit 0."""
    lag_python_repo(royktre.rot, "python-repo")
    lag_rust_repo(royktre.rot, "rust-repo")
    lag_begge_repo(royktre.rot, "begge-repo")
    skriv(royktre.rot / "tomt-repo" / "README.md", "# bare dokumentasjon\n")
    kode, ut = royktre.kjor()
    assert kode == 0
    assert "python-repo: OK (Python)" in ut
    assert "rust-repo: OK (Rust)" in ut
    assert "begge-repo: OK (Python og Rust)" in ut
    assert "tomt-repo: intet å gjøre (ingen kode)" in ut
    assert sammendrag(ok=3, intet=1) in ut


def test_royktest_blandet_tre_gir_riktig_sammendrag_og_uendret_innhold(
    royktre: RoykTre,
) -> None:
    """Blandet tre med alle statusene: sammendraget skal stemme og ingen filer endres.

    ``RoykTre.kjor`` sammenligner innholdet i alle filene i repo-treet før og
    etter kjøringen, også når skriptet finner avvik og skriver ut
    fiks-kommandoer (avklaring 5).
    """
    lag_python_repo(royktre.rot, "python-ok")
    lag_python_repo(royktre.rot, "python-mangler", hook=False)
    python_avvik = lag_python_repo(royktre.rot, "python-avvik")
    skriv(
        python_avvik / "pyproject.toml",
        '[tool.ruff]\nline-length = 79\n\n[tool.ruff.lint]\nignore = ["E501"]\n',
    )
    lag_rust_repo(royktre.rot, "rust-ok")
    rust_mangler = lag_rust_repo(royktre.rot, "rust-mangler")
    (rust_mangler / "tests" / "lint.rs").unlink()
    skriv(royktre.rot / "tomt-repo" / "README.md", "# bare dokumentasjon\n")
    kode, ut = royktre.kjor()
    assert kode != 0
    assert "python-ok: OK (Python)" in ut
    assert "rust-ok: OK (Rust)" in ut
    assert "python-mangler: mangler (Python)" in ut
    assert "rust-mangler: mangler (Rust)" in ut
    assert "python-avvik: avvik (Python)" in ut
    assert "tomt-repo: intet å gjøre (ingen kode)" in ut
    assert "Fiks-kommandoer:" in ut
    assert sammendrag(ok=2, mangler=2, avvik=1, intet=1) in ut


# --- docstringen og de avklarte valgene ---


def test_docstringen_har_avklarte_valg_ikke_apne_valg(skript: object) -> None:
    """Valgene skal være avklarte vedtak, med grunnlag i menneskevedtakene."""
    assert skript.__doc__ is not None
    assert "Avklarte valg" in skript.__doc__
    assert "Avklart ved ferdigstillelsen av sak #3" in skript.__doc__
    assert "skal avklares med mennesket" not in skript.__doc__
    assert "utilities-py#11" in skript.__doc__
    assert "utilities-py#7" in skript.__doc__
    assert "Reelle avvik vinner over exit-kode 2" in skript.__doc__
    assert "--json" in skript.__doc__


def test_markdownlint_hook_varsler_om_tap_foer_overskriving(
    skript: object, tmp_path: Path
) -> None:
    """Overskriving av markdownlint/cspell-hook skal varsle eksplisitt (sak #14 punkt 3)."""
    repo = lag_python_repo(tmp_path, "repo", hook=False)
    skriv_hook(repo / "hooks" / "pre-commit", "#!/bin/sh\nmarkdownlint\ncspell\n")
    referanse = skriv_hook(tmp_path / "utilities-py" / "hooks" / "pre-commit")
    refs = skript.Referanser(python_hook=referanse)
    resultat = skript.Reposultat(
        navn="repo", sti=repo, klassifisering=skript.KLASSE_PYTHON
    )
    skript.sjekk_python(repo, skript.finn_git_rot(repo), refs, resultat)
    tekster = [f.tekst for f in resultat.funn]
    assert any("sak #14 punkt 3" in tekst for tekst in tekster)
    assert any("markdownlint/cspell" in tekst for tekst in tekster)


def test_kombinert_hook_varsler_om_tap_foer_overskriving(
    skript: object, tmp_path: Path
) -> None:
    """Kombinert hook (ruff + markdownlint/cspell) skal varsle eksplisitt (sak #14 punkt 3)."""
    repo = lag_python_repo(tmp_path, "repo", hook=False)
    skriv_hook(
        repo / "hooks" / "pre-commit",
        "#!/bin/sh\nruff check .\nmarkdownlint .\ncspell lint\n",
    )
    referanse = skriv_hook(tmp_path / "utilities-py" / "hooks" / "pre-commit")
    refs = skript.Referanser(python_hook=referanse)
    resultat = skript.Reposultat(
        navn="repo", sti=repo, klassifisering=skript.KLASSE_PYTHON
    )
    skript.sjekk_python(repo, skript.finn_git_rot(repo), refs, resultat)
    tekster = [f.tekst for f in resultat.funn]
    assert any("avviker fra referansen" in tekst for tekst in tekster)
    assert any("sak #14 punkt 3" in tekst for tekst in tekster)
    assert any("markdownlint/cspell" in tekst for tekst in tekster)


def test_ruff_toml_med_exclude_varsler_om_tap(skript: object, tmp_path: Path) -> None:
    """Fjerning av ruff.toml med exclude skal varsle eksplisitt (sak #14 punkt 4)."""
    repo = tmp_path / "repo"
    skriv(repo / "ruff.toml", '# old/ er arkivert\nexclude = ["old"]\n')
    funn = skript.sjekk_python_konfig(repo)
    assert len(funn) == 1
    assert "sak #14 punkt 4" in funn[0].tekst
    assert "exclude" in funn[0].tekst


def test_exclude_advarsel_krever_faktisk_toml_nokkel(skript: object) -> None:
    """Bare faktisk TOML-nøkkel `exclude`/`extend-exclude` skal varsle (sak #14 punkt 4).

    Delstrenger i variabelnavn, verdier og kommentarer er ikke TOML-nøkler
    og skal ikke gi varsel — tidligere substring-søk over-varslet.
    """
    assert skript.exclude_advarsel('exclude = ["old"]\n') is not None
    assert skript.exclude_advarsel('extend-exclude = ["old"]\n') is not None
    assert skript.exclude_advarsel('"exclude" = ["old"]\n') is not None
    assert skript.exclude_advarsel("# exclude holder old/ utenfor\n") is None
    assert skript.exclude_advarsel("line-length = 100 # exclude old/\n") is None
    assert skript.exclude_advarsel('my_exclude = ["old"]\n') is None
    assert skript.exclude_advarsel('ignore = ["exclude"]\n') is None
    assert skript.exclude_advarsel('Exclude = ["old"]\n') is None
