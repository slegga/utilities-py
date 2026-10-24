"""Røyktester for den delbare git pre-commit-hooken (hooks/pre-commit).

Hooken kopieres uendret inn i et tmp-repo og kjøres der — samme
portabilitetskontroll som ved kopiering til et annet repo (sak #5: «kopiere dem
midlertidig til en annen katalog … og kjøre testene der»). Testene verifiserer
at hooken går grønt på ren kode, feiler med tydelig melding ved villet lint-
og formatfeil, blokkerer `git commit`, og håndterer manglende ruff/uvx.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "hooks" / "pre-commit"

REN_MODUL = "x = 1\n"
LINTFEIL = "import os\n"
FORMATFEIL = "x = 'ikke formatert'\n"

RUFF = shutil.which("ruff")
trenger_ruff = pytest.mark.skipif(RUFF is None, reason="ruff finnes ikke på PATH")
trenger_git = pytest.mark.skipif(shutil.which("git") is None, reason="git finnes ikke")


def _min_path(tmp_path):
    """Minimal PATH med verktøyene hooken bruker, men uten ruff og uvx."""
    bin_dir = tmp_path / "minbin"
    bin_dir.mkdir(exist_ok=True)
    for verktoy in ("grep", "printf", "pwd"):
        sti = shutil.which(verktoy)
        if sti is not None:
            (bin_dir / verktoy).symlink_to(sti)
    return str(bin_dir)


def _lag_tmp_repo(tmp_path):
    repo = tmp_path / "repo"
    (repo / "hooks").mkdir(parents=True)
    kopi = repo / "hooks" / "pre-commit"
    shutil.copy(HOOK, kopi)
    kopi.chmod(0o755)
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    return repo


def _skriv_modul(repo, innhold):
    (repo / "modul.py").write_text(innhold, encoding="utf-8")


def _skriv_uvx_shim(tmp_path, navn, innhold):
    bin_dir = tmp_path / navn
    bin_dir.mkdir()
    shim = bin_dir / "uvx"
    shim.write_text("#!/bin/sh\n" + innhold, encoding="utf-8")
    shim.chmod(0o755)
    return str(bin_dir) + os.pathsep + _min_path(tmp_path)


def _kjor_hook(repo, path=None):
    env = dict(os.environ)
    if path is not None:
        env["PATH"] = path
    return subprocess.run(
        [str(repo / "hooks" / "pre-commit")],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def _kjor_git(repo, *args):
    env = dict(os.environ)
    env.update(
        {
            "GIT_AUTHOR_NAME": "royktest",
            "GIT_AUTHOR_EMAIL": "royktest@example.com",
            "GIT_COMMITTER_NAME": "royktest",
            "GIT_COMMITTER_EMAIL": "royktest@example.com",
        }
    )
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


@trenger_ruff
def test_hooken_gaar_gront_paa_ren_kode(tmp_path):
    repo = _lag_tmp_repo(tmp_path)
    _skriv_modul(repo, REN_MODUL)
    resultat = _kjor_hook(repo)
    assert resultat.returncode == 0, resultat.stderr


@trenger_ruff
def test_hooken_feiler_med_tydelig_melding_ved_lintfeil(tmp_path):
    repo = _lag_tmp_repo(tmp_path)
    _skriv_modul(repo, LINTFEIL)
    resultat = _kjor_hook(repo)
    assert resultat.returncode == 1
    assert "ruff check . feilet." in resultat.stderr
    assert "ruff check --fix" in resultat.stderr
    assert "F401" in resultat.stderr


@trenger_ruff
def test_hooken_feiler_med_tydelig_melding_ved_formatfeil(tmp_path):
    repo = _lag_tmp_repo(tmp_path)
    _skriv_modul(repo, FORMATFEIL)
    resultat = _kjor_hook(repo)
    assert resultat.returncode == 1
    assert "ruff format --check . feilet." in resultat.stderr
    assert "Kjør `ruff format`" in resultat.stderr


def test_hooken_feiler_nar_verken_ruff_eller_uvx_finsts(tmp_path):
    repo = _lag_tmp_repo(tmp_path)
    _skriv_modul(repo, REN_MODUL)
    resultat = _kjor_hook(repo, path=_min_path(tmp_path))
    assert resultat.returncode == 1
    assert "ruff er ikke installert." in resultat.stderr
    assert "uvx" in resultat.stderr


@trenger_ruff
def test_hooken_bruker_uvx_fallback_nar_ruff_mangler(tmp_path):
    repo = _lag_tmp_repo(tmp_path)
    _skriv_modul(repo, LINTFEIL)
    path = _skriv_uvx_shim(
        tmp_path,
        "kun_uvx",
        f'if [ "$1" = "ruff" ]; then\n  shift\n  exec "{RUFF}" "$@"\nfi\nexit 1\n',
    )
    resultat = _kjor_hook(repo, path=path)
    assert resultat.returncode == 1
    assert "F401" in resultat.stderr


def test_hooken_gir_tydelig_melding_nar_uvx_ikke_finner_ruff(tmp_path):
    repo = _lag_tmp_repo(tmp_path)
    _skriv_modul(repo, REN_MODUL)
    path = _skriv_uvx_shim(
        tmp_path,
        "uvx_mangler_ruff",
        'echo "  × No solution found when resolving tool dependencies:" >&2\nexit 1\n',
    )
    resultat = _kjor_hook(repo, path=path)
    assert resultat.returncode == 1
    assert "ruff er ikke installert." in resultat.stderr


@trenger_ruff
@trenger_git
def test_hooken_blokkerer_git_commit_ved_lintfeil(tmp_path):
    repo = _lag_tmp_repo(tmp_path)
    subprocess.run(
        ["git", "config", "core.hooksPath", "hooks"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    _skriv_modul(repo, LINTFEIL)
    subprocess.run(
        ["git", "add", "modul.py"], cwd=repo, check=True, capture_output=True
    )
    blokkert = _kjor_git(repo, "commit", "-m", "skal blokkeres")
    assert blokkert.returncode != 0
    assert "ruff check . feilet." in blokkert.stderr

    _skriv_modul(repo, REN_MODUL)
    subprocess.run(
        ["git", "add", "modul.py"], cwd=repo, check=True, capture_output=True
    )
    godkjent = _kjor_git(repo, "commit", "-m", "skal godkjennes")
    assert godkjent.returncode == 0, godkjent.stderr
