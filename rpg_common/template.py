from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

SORT_FALLBACK_OFFSET = 1000


def load_rekkefoelge(path: Path) -> list[str]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _fallback_sort_key(key: str) -> int:
    return SORT_FALLBACK_OFFSET + ord(key[0]) if key else SORT_FALLBACK_OFFSET


def mytextsort(items: list[str], rekkefoelge: list[str]) -> list[str]:
    if not items:
        return []
    lookup: dict[str, int] = {}
    for item in items:
        try:
            lookup[item] = rekkefoelge.index(item)
        except ValueError:
            lookup[item] = _fallback_sort_key(item)
    return sorted(items, key=lambda x: lookup[x])


def myrowsort(
    data: list[dict[str, Any]],
    rekkefoelge: list[str],
    sort_columns: list[str] | None = None,
) -> list[dict[str, Any]]:
    if not data:
        return []
    lookup: dict[int, int] = {}
    for i, row in enumerate(data):
        found = False
        if sort_columns:
            for col in sort_columns:
                if col in row:
                    val = str(row[col])
                    digits = "".join(c for c in val if c.isdigit())
                    if digits:
                        lookup[i] = int(digits)
                        found = True
                        break
        if not found:
            navn = row.get("navn", "")
            try:
                lookup[i] = rekkefoelge.index(navn)
            except ValueError:
                lookup[i] = _fallback_sort_key(str(navn))
    return [data[i] for i in sorted(range(len(data)), key=lambda x: lookup[x])]


def gterning(
    number: int, offset: int = 1, range_: int = 1
) -> tuple[int, str]:
    start = offset
    end = start + range_ - 1
    text = str(start) if start == end else f"{start}-{end}"
    return end + 1, text


def ctable(
    data: list[dict[str, Any]],
    category: str,
    columns: list[str] | None = None,
    calculated: dict[str, Any] | None = None,
    rekkefoelge: list[str] | None = None,
) -> str:
    if not data:
        return ""
    if columns is None:
        columns = mytextsort(list(data[0].keys()), rekkefoelge or [])

    lines: list[str] = []
    header = "|" + "|".join(columns) + "|"
    sep = "|" + "|".join("-" for _ in columns) + "|"
    lines.append(header)
    lines.append(sep)

    for row in data:
        vals = []
        for col in columns:
            val = row.get(col, "")
            vals.append(str(val) if val is not None else "")
        lines.append("|" + "|".join(vals) + "|")

    return "\n".join(lines)


def clist(
    data: list[dict[str, Any]],
    category: str,
    bindword: str = "og",
    rekkefoelge: list[str] | None = None,
) -> str:
    names = [row["navn"] for row in data if "navn" in row]
    sorted_names = mytextsort(names, rekkefoelge or [])
    if len(sorted_names) <= 1:
        return "".join(sorted_names)
    return ", ".join(sorted_names[:-1]) + f" {bindword} " + sorted_names[-1]
