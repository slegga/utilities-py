"""Delbar lint-test som kjører ruff check og ruff format --check som del av
de lokale testene.

Kopier filen uendret inn i `tests/` (eller `test/`) i et hvilket som helst
Python-repo. Krever `ruff` — som dev-avhengighet i prosjektet, eller `uvx`
på PATH som fallback.

Ruff-konfigurasjonen (`ruff.toml`) kopieres sammen med denne filen og leses
av ruff på standard vis. Denne filen er konfigurasjonsløs: den finner
prosjektroten relativt til testfilen og kjører ruff derfra. Filen er selv
kompatibel med ruff standardkonfigurasjon (linjelengde 88, default select)
og inneholder ikke tvetydige unicode-tegn, slik at den også passer inn i
repoer med egen ruff-konfigurasjon.

## Ruff-nivå

Regelsettet styres av `select`/`ignore` i `ruff.toml` som kopieres sammen med
denne filen, og er satt så komplett som praktisk mulig: både `ruff check` med
bredt regelsett og `ruff format --check`.

Er regelsettet for strengt for et repo som tar filen i bruk, er det `ruff.toml`
som styrer nivået — ikke denne filen. Hvor streng linten skal være er et valg
som bør avklares med den som eier kravet, ikke avgjøres stille her.

## Røyktester

Filen inneholder røyktester som verifiserer at lint-testen faktisk feiler på
villette lint- og formatfeil med tydelig melding om hva som må fikses, og at den
ellers går grønt. Røyktestene skriver alltid en fast, kjent minimal
ruff-konfigurasjon til det temporære prosjektet. Det gjør dem uavhengige av
hvilken ruff-konfigurasjon målrepoet ellers har, og isolerer dem samtidig fra
bruker- og systemkonfigurasjonen til ruff. Forutsetningene røyktestene hviler
på er satt eksplisitt i den faste konfigurasjonen: `ruff check` fanger ubrukte
importer (F401), og `ruff format` krever doble sitater.

## Vedlikehold

Vedlikeholdet av denne filen deles av agent og menneske.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

INSTALL_RUFF = (
    "Legg ruff til som dev-avhengighet, for eksempel `uv add --dev ruff` "
    "eller `uv add --optional dev ruff`."
)

UV_FEILMELDINGER = (
    "no solution found when resolving tool dependencies",
    "was not found in the package registry",
    "failed to fetch",
    "failed to download",
)
OS_FEILMELDING = re.compile(
    r"^(?:no such file or directory|command not found)(?: \(os error \d+\))?$",
)


def project_root() -> Path:
    """Prosjektroten er katalogen over testkatalogen (tests/ eller test/)."""
    return Path(__file__).resolve().parent.parent


def ruff_command() -> list[str]:
    """Finn ruff: installert ruff først, deretter `uvx ruff` som fallback."""
    ruff = shutil.which("ruff")
    if ruff:
        return [ruff]
    uvx = shutil.which("uvx")
    if uvx:
        return [uvx, "ruff"]
    return []


def run(cmd: list[str], root: Path) -> subprocess.CompletedProcess:
    """Kjør en kommando i prosjektroten og returner resultatet."""
    cmdline = " ".join(cmd)
    try:
        return subprocess.run(
            cmd,
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as err:
        detaljer = f"Sjekk at {cmd[0]} er installert og ligger på PATH.\nFeil: {err}"
        melding = f"Klarte ikke å kjøre kommandoen {cmdline}.\n{detaljer}"
        raise AssertionError(melding) from err


def output_text(output: subprocess.CompletedProcess) -> str:
    """Tekstlig visning av et kommandoresultat, til bruk i feilmeldinger."""
    if output.returncode < 0:
        status = f"avbrutt av signal {-output.returncode}"
    else:
        status = f"exit status: {output.returncode}"
    stdout = output.stdout
    stderr = output.stderr
    return f"{status}\n\n--- stdout ---\n{stdout}\n--- stderr ---\n{stderr}"


def error_message(line: str) -> str | None:
    """Meldingsdelen etter feil-markøren, eller None hvis linjen ikke er markert."""
    if line.startswith("error: "):
        return line.removeprefix("error: ").strip()
    stripped = line.strip()
    if stripped.startswith(("\u00d7", "\u2570")):
        return stripped.lstrip("\u00d7\u2570\u2500\u25b6 ").strip()
    return None


def is_missing_tool_error(stderr: str) -> bool:
    """Sann hvis stderr-en ser ut til å bety at selve verktøyet mangler.

    Gjenkjenningen er begrenset til faktiske manglende-verktøy-meldinger, det
    vil si linjer som starter med `error: ` eller med en av uv/uvx sine egne
    feil-markører.

    For uv/uvx-mønstrene (no solution found when resolving tool dependencies,
    was not found in the package registry, failed to fetch, failed to download)
    holder det at mønsteret nevnes et sted i meldingen.

    For operativsystemmønstrene (no such file or directory, command not found)
    må hele meldingen være nettopp OS-feilen, eventuelt med `(os error N)` til
    slutt. Det skiller «ruff er ikke installert» fra ruff sine egne IO-feil,
    for eksempel `error: Failed to read `fil.py`: No such file or directory`.

    Treff på tekst inne i kodeutdrag (f.eks. en strengvariabel med samme ordlyd)
    ignoreres fordi slike linjer ikke starter med en av feil-markørene.
    """
    for line in stderr.splitlines():
        text = error_message(line)
        if text is None:
            continue
        lower = text.lower()
        if any(m in lower for m in UV_FEILMELDINGER):
            return True
        if OS_FEILMELDING.fullmatch(lower):
            return True
    return False


def missing_tool_message(
    output: subprocess.CompletedProcess,
    tool: str,
    install_command: str,
) -> str | None:
    """Returner en feilmelding hvis kommandoen feilet fordi verktøyet mangler.

    Sjekken kjøres bare når kommandoen faktisk feilet.
    """
    if output.returncode == 0:
        return None
    if is_missing_tool_error(output.stderr):
        details = output_text(output)
        return f"{tool} er ikke installert.\n\n{install_command}\n\n{details}"
    return None


def assert_ruff_check(root: Path) -> None:
    """Kjør `ruff check .` i root og feil med tydelig melding hvis det er avvik."""
    cmd = ruff_command()
    assert cmd, f"ruff er ikke installert.\n\n{INSTALL_RUFF}\n"
    output = run([*cmd, "check", "."], root)
    message = missing_tool_message(output, "ruff", INSTALL_RUFF)
    if message is not None:
        raise AssertionError(message)
    assert output.returncode == 0, (
        f"ruff check . feilet.\n\n"
        f"Fiks varslene som er listet opp nedenfor, for eksempel med "
        f"`ruff check --fix`,\n"
        f"og kjør `ruff check .` for å bekrefte at alt er rettet.\n\n"
        f"Arbeidskatalog: {root}\n\n{output_text(output)}"
    )


def assert_ruff_format(root: Path) -> None:
    """Kjør `ruff format --check .` i root og feil hvis koden ikke er formatert."""
    cmd = ruff_command()
    assert cmd, f"ruff er ikke installert.\n\n{INSTALL_RUFF}\n"
    output = run([*cmd, "format", "--check", "."], root)
    message = missing_tool_message(output, "ruff", INSTALL_RUFF)
    if message is not None:
        raise AssertionError(message)
    assert output.returncode == 0, (
        f"ruff format --check . feilet.\n\n"
        f"Koden er ikke formatert med ruff. Kjør `ruff format` for å rette\n"
        f"formateringen automatisk, deretter `ruff format --check .` for å\n"
        f"bekrefte at alt er rettet.\n\n"
        f"Arbeidskatalog: {root}\n\n{output_text(output)}"
    )


def test_ruff_check() -> None:
    assert_ruff_check(project_root())


def test_ruff_format() -> None:
    assert_ruff_format(project_root())


# --- Røyktester: lint-testen skal fange villete lint- og formatfeil ---


# Fast, kjent minimal ruff-konfigurasjon som alltid brukes i røyktestene.
# Premissene røyktestene hviler på er satt eksplisitt her: `ruff check`
# fanger ubrukte importer (F401), og `ruff format` krever doble sitater.
ROYKTEST_RUFF_TOML = """\
[lint]
select = ["F"]

[format]
quote-style = "double"
"""


def make_project(root: Path, source: str) -> None:
    """Opprett et lite prosjekt i root med én modul med gitt kildekode.

    Den faste, kjente konfigurasjonen skrives alltid til det temporære
    prosjektet, slik at røyktestene er uavhengige av hvilken
    ruff-konfigurasjon målrepoet ellers har.
    """
    (root / "modul.py").write_text(source, encoding="utf-8")
    (root / "ruff.toml").write_text(ROYKTEST_RUFF_TOML, encoding="utf-8")


def failed_check(action: Callable[[], None], context: str) -> str:
    """Kjør en sjekk som forventes å feile, og returner feilmeldingen."""
    try:
        action()
    except AssertionError as err:
        return str(err)
    raise AssertionError(f"{context} skulle ha feilet, men gikk grønt.")


def test_royktest_villet_lintfeil_feiler() -> None:
    """En villet lintfeil skal få lint-testen til å feile med tydelig melding."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        make_project(root, "import os\n")
        message = failed_check(
            lambda: assert_ruff_check(root),
            "lint-testen på et prosjekt med villet lintfeil",
        )
    assert "ruff check . feilet" in message
    assert "ruff check --fix" in message


def test_royktest_villet_formatfeil_feiler() -> None:
    """En villet formatfeil skal få format-sjekken til å feile med tydelig melding."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        make_project(root, "x = 'ikke formatert'\n")
        message = failed_check(
            lambda: assert_ruff_format(root),
            "format-sjekken på et prosjekt med villet formatfeil",
        )
    assert "ruff format --check . feilet" in message
    assert "Kjør `ruff format`" in message


def test_royktest_rent_prosjekt_gar_gront() -> None:
    """Et prosjekt uten avvik skal gå grønt på både lint og format."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        make_project(root, "x = 1\n")
        assert_ruff_check(root)
        assert_ruff_format(root)


# --- Tester for gjenkjenning av manglende verktøy ---


def failed_output(stderr: str) -> subprocess.CompletedProcess:
    """Returner et resultat som ser ut som en feilet kommando med gitt stderr."""
    return subprocess.CompletedProcess(
        args=["ruff", "check", "."],
        returncode=2,
        stdout="",
        stderr=stderr,
    )


def test_missing_tool_message_fanger_uvx_og_os_meldinger() -> None:
    # Meldingsform 1: uvx/uv sin "no solution found" (verktøyet finnes ikke
    # i registret, eller avhengighetene kan ikke løses).
    uvx_form = "  \u00d7 No solution found when resolving tool dependencies\n"
    # Meldingsform 2: operativsystemet sin "no such file or directory".
    os_form = "error: No such file or directory (os error 2)\n"
    for stderr in (uvx_form, os_form):
        output = failed_output(stderr)
        message = missing_tool_message(output, "ruff", INSTALL_RUFF)
        assert message is not None, f"bør gjenkjennes:\n{stderr}"
        assert "ruff er ikke installert" in message, f"skal nevne verktøy:\n{message}"
        assert INSTALL_RUFF in message, f"skal ha hint om installering:\n{message}"


def test_is_missing_tool_error_fanger_ovrige_uvx_meldinger() -> None:
    tilfeller = [
        "  \u00d7 Failed to fetch: `ruff`\n",
        "  \u00d7 Failed to download `ruff`\n",
        "  \u2570\u2500\u25b6 Because ruff was not found in the package registry\n",
        "error: command not found\n",
    ]
    for stderr in tilfeller:
        assert is_missing_tool_error(stderr), f"bør gjenkjennes:\n{stderr}"


def test_is_missing_tool_error_ignorerer_vanlige_feil() -> None:
    # Vanlige lint-/formatfeil skal ikke rapporteres som manglende verktøy.
    stderr = "F401 `os` imported but unused\n --> modul.py:2:1\n"
    assert not is_missing_tool_error(stderr)
    # Mønstre som bare dukker opp som tekst (f.eks. i et kodeutdrag) skal heller
    # ikke utløse, fordi linjen ikke starter med en feil-markør.
    stderr = 'modul.py\n error: failed to fetch\n    "failed to fetch",\n'
    assert not is_missing_tool_error(stderr)
    # ruff sine egne IO-feil er ikke manglende verktøy.
    stderr = "error: Failed to read `modul.py`: No such file or directory\n"
    assert not is_missing_tool_error(stderr)
