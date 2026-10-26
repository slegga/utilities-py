"""Home-made LastPass CSV reader.

Python port of the Perl ``SH::CSVLastPass`` module. Unlike a standard CSV
parser this also handles LastPass exports where a field spans several physical
lines *without* being quoted (the parser keeps reading until the row has the
expected number of columns), as well as the usual RFC-4180 quoted multi-line
fields.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def _perl_split(string: str, sep: str) -> list[str]:
    """Split like Perl ``split /sep/, $str`` (trailing empty fields removed)."""
    parts = string.split(sep)
    while parts and parts[-1] == "":
        parts.pop()
    return parts


class CSVLastPass:
    """Reader for LastPass-style CSV files."""

    def read(
        self, file: str, args: dict[str, Any] | None = None
    ) -> list[dict[str, str]]:
        """Read ``file`` and return a list of row dicts keyed by header column."""
        args = args or {}
        sep = args.get("sep_char", ",")
        quote = args.get("quote_char", '"')
        where_to_put_extra = args.get("column_with_extra")

        close_re = re.compile(
            f"(?<!{re.escape(quote)}){re.escape(quote)}{re.escape(sep)}"
        )

        hashes: list[dict[str, str]] = []
        keys: list[str] = []
        first_line = True
        inrow = False
        inquote = False

        lines = Path(file).read_text(encoding="utf-8").split("\n")
        # A trailing newline yields a final empty element; drop it like chomp+EOF.
        if lines and lines[-1] == "":
            lines.pop()

        for line in lines:
            if inrow:
                i = len(hashes[-1]) - 1
                if i > len(keys) - 1:
                    raise ValueError("Too many columns in continuation row")
                vals = line.split(sep)  # keep trailing empties (Perl split ... -1)
                if not vals:
                    if hashes[-1].get(keys[i]):
                        hashes[-1][keys[i]] += "\n"
                    continue
                hashes[-1][keys[i]] = (
                    (hashes[-1].get(keys[i], "") + "\n")
                    if hashes[-1].get(keys[i])
                    else ""
                ) + vals[0]
                if len(vals) == 1:
                    continue
                for j in range(1, len(vals)):
                    if not keys[i + j]:
                        raise NotImplementedError("Unmapped extra column")
                    hashes[-1][keys[i + j]] = vals[j]
                if len(hashes[-1]) == len(keys):
                    inrow = False
                else:
                    raise ValueError(
                        f"Keys: {'-'.join(hashes[-1].keys())} == {'-'.join(keys)}"
                    )
                continue

            if inquote:
                i = len(hashes[-1]) - 1
                if i > len(keys) - 1:
                    raise ValueError("Too many columns in quoted continuation")
                if not close_re.search(line):
                    hashes[-1][keys[i]] = hashes[-1].get(keys[i], "") + line + "\n"
                else:
                    data, rest_line = close_re.split(line, 1)
                    hashes[-1][keys[i]] = hashes[-1].get(keys[i], "") + data
                    i += 1
                    vals = rest_line.split(sep)
                    for j in range(i, len(keys)):
                        hashes[-1][keys[j]] = vals[j - i]
                    inquote = False
                continue
            elif first_line:
                keys = line.split(sep)
                first_line = False
            elif (sep + quote) in line or line[:1] == quote:
                inquote = self._quoted_row(line, hashes, keys, sep, quote)
            else:
                inrow = self._plain_row(line, hashes, keys, sep, where_to_put_extra)

        return hashes

    def _continue_row(
        self, line: str, hashes: list[dict[str, str]], keys: list[str], sep: str
    ) -> bool:
        """Fortsett en rad over flere linjer. Returnerer ny verdi for ``inrow``."""
        i = len(hashes[-1]) - 1
        if i > len(keys) - 1:
            raise ValueError("Too many columns in continuation row")
        vals = line.split(sep)  # keep trailing empties (Perl split ... -1)
        if not vals:
            if hashes[-1].get(keys[i]):
                hashes[-1][keys[i]] += "\n"
            return True
        hashes[-1][keys[i]] = (
            (hashes[-1].get(keys[i], "") + "\n") if hashes[-1].get(keys[i]) else ""
        ) + vals[0]
        if len(vals) == 1:
            return True
        for j in range(1, len(vals)):
            if not keys[i + j]:
                raise NotImplementedError("Unmapped extra column")
            hashes[-1][keys[i + j]] = vals[j]
        if len(hashes[-1]) == len(keys):
            return False
        raise ValueError(f"Keys: {'-'.join(hashes[-1].keys())} == {'-'.join(keys)}")

    def _continue_quoted(
        self,
        line: str,
        hashes: list[dict[str, str]],
        keys: list[str],
        sep: str,
        close_re: re.Pattern,
    ) -> bool:
        """Fortsett et sitert felt over flere linjer. Returnerer ny ``inquote``."""
        i = len(hashes[-1]) - 1
        if i > len(keys) - 1:
            raise ValueError("Too many columns in quoted continuation")
        if not close_re.search(line):
            hashes[-1][keys[i]] = hashes[-1].get(keys[i], "") + line + "\n"
            return True
        data, rest_line = close_re.split(line, 1)
        hashes[-1][keys[i]] = hashes[-1].get(keys[i], "") + data
        i += 1
        vals = rest_line.split(sep)
        for j in range(i, len(keys)):
            hashes[-1][keys[j]] = vals[j - i]
        return False

    def _quoted_row(
        self,
        line: str,
        hashes: list[dict[str, str]],
        keys: list[str],
        sep: str,
        quote: str,
    ) -> bool:
        """Start en rad med siterte felt. Returnerer ny ``inquote``."""
        row: dict[str, str] = {}
        i = -1
        if (quote + sep) in line:
            if (sep + quote) in line:
                prerest, rest = line.split(sep + quote, 1)
            else:
                prerest, rest = line.split(quote, 1)
            if prerest:
                vals = prerest.split(sep)
                for idx, val in enumerate(vals):
                    row[keys[idx]] = val
                i = len(vals) - 1
            quote_val, rest = rest.split(quote + sep, 1)
            i += 1
            row[keys[i]] = quote_val
            i += 1
            vals = rest.split(sep)
            for j, val in enumerate(vals):
                row[keys[i + j]] = val
            hashes.append(row)
            return False
        rest, data = re.split(f"{re.escape(sep)}?{re.escape(quote)}", line, maxsplit=1)
        vals = rest.split(sep)
        for idx, val in enumerate(vals):
            row[keys[idx]] = val
        row[keys[len(vals)]] = row.get(keys[len(vals)], "") + data + "\n"
        hashes.append(row)
        return True

    def _plain_row(
        self,
        line: str,
        hashes: list[dict[str, str]],
        keys: list[str],
        sep: str,
        where_to_put_extra: str | None,
    ) -> bool:
        """Start en usitert rad. Returnerer ny ``inrow``."""
        vals = _perl_split(line, sep)
        if len(keys) == len(vals):
            hashes.append({keys[idx]: val for idx, val in enumerate(vals)})
            return False
        if len(keys) < len(vals):
            if not where_to_put_extra:
                raise ValueError("Too many columns; do not know what to do")
            extra = len(vals) - len(keys)
            row: dict[str, str] = {}
            j = 0
            for val in vals:
                if keys[j] != where_to_put_extra:
                    row[keys[j]] = val
                else:
                    row[keys[j]] = row.get(keys[j], "") + val
                    if extra:
                        continue
                    extra -= 1
                j += 1
            hashes.append(row)
            return False
        # len(keys) > len(vals): multi-line row starts here
        hashes.append({keys[idx]: val for idx, val in enumerate(vals)})
        return True
