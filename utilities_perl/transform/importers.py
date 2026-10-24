"""Importer plugins for :mod:`utilities_perl.transform`."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from ..csv_lastpass import CSVLastPass


def _extname(path: Any) -> str:
    return Path(str(path)).suffix.lstrip(".")


class Importer:
    """Base class for importer plugins."""

    def is_accepted(self, args: dict) -> bool:
        raise NotImplementedError(f"{type(self).__name__}.is_accepted is not defined")

    def importx(self, args: dict) -> Any:
        raise NotImplementedError(f"{type(self).__name__}.importx is not defined")


class CSVLastPassImporter(Importer):
    """Import a LastPass-style CSV file via :class:`CSVLastPass`."""

    def is_accepted(self, args: dict) -> bool:
        return _extname(args.get("file", "")) == "csv"

    def importx(self, args: dict) -> list[dict[str, str]]:
        opts = {k: v for k, v in args.items() if k != "file"}
        opts["column_with_extra"] = "url"
        return CSVLastPass().read(args["file"], opts)


class JSONImporter(Importer):
    """Import a JSON file."""

    def is_accepted(self, args: dict) -> bool:
        return _extname(args.get("file", "")) == "json"

    def importx(self, args: dict) -> Any:
        return json.loads(Path(args["file"]).read_text(encoding="utf-8"))


class SQLiteTableImporter(Importer):
    """Import every row of a SQLite table as a list of dicts."""

    def is_accepted(self, args: dict) -> bool:
        return "type" in args and str(args["type"]).lower() == "sqlitetable"

    def importx(self, args: dict) -> list[dict[str, Any]]:
        conn = sqlite3.connect(args["file"])
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(f"select * from {args['table']}").fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()
