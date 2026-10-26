"""Templatehjelpere for RPG-dokumenter.

Gir rene Python-funksjoner som kan brukes i Jinja2-maler for å generere
Markdown-tabeller, lister og terningområder basert på YAML-data.

Port av Perl-hjelperne i ``osr-rpg/bin/md-update.pl`` og
``mm-rpg/src/genererte-tabeller.conf``.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import yaml

SORT_FALLBACK_OFFSET = 1000


def load_rekkefoelge(path: Path | str) -> list[str]:
    """Last en ``rekkefoelge.list.yml``-fil og returner sorteringslisten.

    Parameters
    ----------
    path:
        Sti til YAML-filen som inneholder en liste med nøkkelord
        i ønsket rekkefølge.

    Returns
    -------
    list[str]:
        Sorteringslisten, eller tom liste hvis filen ikke finnes.
    """
    p = Path(path)
    if not p.exists():
        return []
    with open(p, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if isinstance(data, list):
        return [str(item) for item in data]
    return []


def mytextsort(items: Sequence[str], rekkefoelge: Sequence[str]) -> list[str]:
    """Sorter en liste med nøkkelord etter definert rekkefølge.

    Elementer som ikke finnes i *rekkefoelge* får fallback-verdi
    (1000 + ASCII-verdien av første tegn) og plasseres sist.

    Parameters
    ----------
    items:
        Strenger som skal sorteres.
    rekkefoelge:
        Definert rekkefølge (f.eks. lastet fra ``rekkefoelge.list.yml``).

    Returns
    -------
    list[str]:
        Sortert kopi av *items*.
    """
    lookup: dict[str, int] = {}
    for item in items:
        try:
            idx = rekkefoelge.index(item)
        except ValueError:
            idx = SORT_FALLBACK_OFFSET + ord(item[0]) if item else SORT_FALLBACK_OFFSET
        lookup[item] = idx
    return sorted(items, key=lambda x: lookup[x])


def myrowsort(
    data: dict[str, Any],
    rekkefoelge: Sequence[str],
    sort_columns: Sequence[str] | None = None,
) -> list[str]:
    """Sorter rader (hash-nøkler) etter en kolonne eller etter rekkefølge-filen.

    Først sjekkes om det finnes en *sort_columns*-liste med kolonner å
    sortere etter -- i så fall brukes første treffende kolonne med et
    tall som sort-key. Fallback til ``rekkefoelge``-basert sortering.

    Parameters
    ----------
    data:
        Dict der nøklene er radnavn og verdiene er dicts med feltverdier.
    rekkefoelge:
        Definert rekkefølge for fallback-sortering.
    sort_columns:
        Kolonner å sjekke for numerisk sortering (rekkefølge betyr ikke noe).

    Returns
    -------
    list[str]:
        Sorterte radnøkler.
    """
    if sort_columns:
        for sort_col in sort_columns:
            if any(sort_col in row for row in data.values()):
                lookup: dict[str, int] = {}
                for key, row in data.items():
                    val = row.get(sort_col, "")
                    if isinstance(val, str):
                        m = re.search(r"(\d+)", val)
                        if m:
                            lookup[key] = int(m.group(1))
                        else:
                            lookup[key] = (
                                SORT_FALLBACK_OFFSET + ord(key[0])
                                if key
                                else SORT_FALLBACK_OFFSET
                            )
                    elif isinstance(val, (int, float)):
                        lookup[key] = int(val)
                    else:
                        lookup[key] = (
                            SORT_FALLBACK_OFFSET + ord(key[0])
                            if key
                            else SORT_FALLBACK_OFFSET
                        )
                return sorted(data.keys(), key=lambda x: lookup[x])

    # Fallback: bruk rekkefoelge
    return mytextsort(list(data.keys()), rekkefoelge)


def ctable(
    data: Sequence[dict[str, Any]],
    category: str,
    columns: list[str] | None = None,
    calculated: dict[str, Callable] | None = None,
    rekkefoelge: Sequence[str] | None = None,
) -> str:
    """Generer en Markdown-tabell fra en kategori med data.

    Parameters
    ----------
    data:
        Liste med dicts, der hver dict er en rad.
    category:
        Kategorinavn (brukes som overskrift for ``navn``-kolonnen).
    columns:
        Kolonner som skal vises. Hvis None, auto-detekteres fra første rad
        og sorteres etter *rekkefoelge*.
    calculated:
        Beregnede kolonner som tar ``(category, row)`` som argument.
    rekkefoelge:
        Sorteringsliste for kolonne-rekkefølge.

    Returns
    -------
    str:
        Markdown-tabell som streng.
    """
    if not data:
        return ""

    if columns is None:
        first_row = data[0]
        if not isinstance(first_row, dict):
            raise TypeError(f"{category} is missing keys")
        if rekkefoelge is not None:
            columns = mytextsort(list(first_row.keys()), rekkefoelge)
        else:
            columns = sorted(first_row.keys())

    if calculated:
        data = [dict(row) for row in data]
        for row in data:
            for key, func in calculated.items():
                row[key] = func(category, row)

    lines: list[str] = []
    header = "|".join([""] + [category if c == "navn" else c for c in columns] + [""])
    sep = "|".join([""] + ["-"] * len(columns) + [""])
    lines.append(header)
    lines.append(sep)

    for row in data:
        values: list[str] = []
        for c in columns:
            data_key = "navn" if c == category else c
            val = row.get(data_key, "")
            if callable(val):
                val = val(category, row)
            values.append(str(val) if val is not None else " ")
        lines.append("|".join(["", *values, ""]))

    return "\n".join(lines)


def clist(
    data: Sequence[dict[str, Any]],
    category: str,
    bindword: str = "og",
    rekkefoelge: Sequence[str] | None = None,
) -> str:
    """Generer en norsk sammenkjedet liste av navn fra en kategori.

    Parameters
    ----------
    data:
        Liste med dicts, der hver dict har et ``navn``-felt.
    category:
        Kategorinavn (for feilmeldinger).
    bindword:
        Bindord som skiller siste element (standard: ``og``).
    rekkefoelge:
        Sorteringsliste for navn-rekkefølge.

    Returns
    -------
    str:
        Sammenkjedet liste, f.eks. ``"A, B og C"``.
    """
    names = [item["navn"] for item in data]
    sorted_names = (
        mytextsort(names, rekkefoelge) if rekkefoelge is not None else sorted(names)
    )
    if len(sorted_names) == 1:
        return sorted_names[0]
    last = sorted_names[-1]
    rest = sorted_names[:-1]
    return ", ".join(rest) + " " + bindword + " " + last


def gterning(number: int, offset: int = 1, range_: int = 1) -> tuple[int, str]:
    """Generer terningområde-tekst for en fordeling over *number* terningslag.

    Port av Perl-funksjonen i ``osr-rpg/bin/md-update.pl``.

    Parameters
    ----------
    number:
        Antall terninger (brukes ikke direkte, men beholdt for API-kompatibilitet).
    offset:
        Gjeldende offset (startverdi for området).
    range_:
        Antall ganger noe forekommer (lengde på området).

    Returns
    -------
    tuple[int, str]:
        Oppdatert offset og tekst som ``"start-slutt"`` eller enkelttall.

    Raises
    ------
    ValueError
        Hvis *range_* er mindre enn 1.
    """
    if range_ < 1:
        raise ValueError("range is less than 1")
    start = offset
    end = start + range_ - 1
    text = str(start) if start == end else f"{start}-{end}"
    return end + 1, text
