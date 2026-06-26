"""Exporter plugins for :mod:`utilities_perl.transform`."""

from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Any

import yaml

from ..ask import ask
from ..passcode import PassCodeFile


def _extname(path: Any) -> str:
    return Path(str(path)).suffix.lstrip(".")


class Exporter:
    """Base class for exporter plugins."""

    def is_accepted(self, args: dict) -> bool:
        raise NotImplementedError(f"{type(self).__name__}.is_accepted is not defined")

    def export(self, args: dict, data: Any) -> Any:
        raise NotImplementedError(f"{type(self).__name__}.export is not defined")


class YAMLExporter(Exporter):
    """Write data to a YAML file."""

    def is_accepted(self, args: dict) -> bool:
        if not args.get("file"):
            return False
        return _extname(args["file"]) in ("yaml", "yml")

    def export(self, args: dict, data: Any) -> Any:
        if not args.get("file"):
            raise ValueError("Missing argument file")
        with open(args["file"], "w", encoding="utf-8") as fh:
            yaml.safe_dump(data, fh, allow_unicode=True, default_flow_style=False)
        return data


class PassCodeExporter(Exporter):
    """Write data into a pass code store."""

    def is_accepted(self, args: dict) -> bool:
        return "type" in args and str(args["type"]).lower() == "passcode"

    def export(self, args: dict, data: Any) -> None:
        formatted: list[dict[str, Any]] = []
        if data and data[0].get("name"):
            accepted = {"grouping", "name", "password", "username", "url", "totp", "fav", "extra"}
            for row in data:
                for key in row:
                    if key not in accepted:
                        raise ValueError(f"Unknown key: {key} in Last Pass format")
                nr: dict[str, Any] = {}
                nr["filepath"] = (
                    f"{row['grouping']}/{row['name']}" if row.get("grouping") else row["name"]
                )
                for key in ("password", "username", "url"):
                    nr[key] = row.get(key)
                nr["changed"] = time.strftime("%Y-%m-%d")
                nr["comment"] = row.get("extra")
                if row.get("totp"):
                    nr["comment"] = (nr["comment"] or "") + ",totp:" + row["totp"]
                if row.get("fav"):
                    nr["comment"] = (nr["comment"] or "") + ",fav:" + str(row["fav"])
                if args.get("dir"):
                    nr["dir"] = args["dir"]
                if not nr.get("filepath"):
                    if sum(1 for v in nr.values() if v is not None) == 2:
                        continue
                    raise ValueError("Missing file path")
                if re.search(r"jobb|Business", nr["filepath"], re.I):
                    nr["filepath"] = "jobb/" + os.path.basename(nr["filepath"])
                formatted.append(nr)
        elif data and "SYSTEM" in data[0]:
            accepted = {"id", "DOMENE", "GRUPPERING", "SYSTEM", "URL", "BRUKER", "PASSORD", "BESKRIVELSE", "BYTTE"}
            for row in data:
                for key in row:
                    if key not in accepted:
                        raise ValueError(f"Unknown key: {key} in passordfil format")
                filename = row.get("SYSTEM") or row.get("url")
                if filename is None:
                    raise ValueError("missing filename source")
                filename = re.sub(r"\s", "_", filename)
                filename = re.sub(r"^https?+://", "", filename)
                filename = re.sub(r"[/:].*", "", filename)
                if not filename:
                    if not row.get("password"):
                        continue
                    raise ValueError("No filename")
                nr = {
                    "filepath": (row.get("GRUPPERING") or row.get("DOMENE")) + "/" + filename,
                    "password": row.get("PASSORD"),
                    "username": row.get("BRUKER"),
                    "url": row.get("URL"),
                    "changed": row.get("BYTTE"),
                    "comment": row.get("BESKRIVELSE"),
                }
                if args.get("dir"):
                    nr["dir"] = args["dir"]
                formatted.append(nr)

        for entry in formatted:
            self._check_duplicate_and_store_file(entry, args)

    def _check_duplicate_and_store_file(self, f: dict[str, Any], args: dict) -> None:
        if not f.get("filepath"):
            raise ValueError("Missing filepath")
        existing = PassCodeFile.from_file(f["filepath"], args)
        if not existing:
            PassCodeFile(**f).to_file(args)
            return

        diff = any(
            f.get(k) and getattr(existing, k, None) and getattr(existing, k) != f.get(k)
            for k in PassCodeFile.okeys()
        )
        if not diff:
            return
        print("Duplicate filename: " + f["filepath"])
        keep = ask(
            "Which one do you want to keep? [1, 2, b=both, e=edit-file-2, q=quit]: ",
            [1, 2, "b", "e", "q"],
        )
        if keep == "q":
            print("User exit")
            raise SystemExit
        if keep == "1":
            return
        if keep == "b":
            f["filepath"] += "-" + (f.get("username") or "")
        elif keep == "e":
            old = os.path.basename(f["filepath"])
            dir_ = os.path.dirname(f["filepath"])
            new = ask(f"Enter new filename old is {old}: ", re.compile(r".*"))
            f["filepath"] = (dir_ + "/" if dir_ else "") + new

        for k in PassCodeFile.okeys():
            if f.get(k):
                setattr(existing, k, f[k])
        existing.to_file()
