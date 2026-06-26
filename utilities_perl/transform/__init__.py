"""Transform data from one source/format to another.

Python port of the Perl ``SH::Transform`` framework. Importers read data into a
list of dicts; exporters write that data out. Plugins are selected
automatically based on the importer/exporter arguments (file extension or an
explicit ``type``), mirroring ``Module::Pluggable`` behaviour.
"""

from __future__ import annotations

import json
from typing import Any

from .importers import CSVLastPassImporter, JSONImporter, SQLiteTableImporter
from .exporters import PassCodeExporter, YAMLExporter

IMPORTERS = [CSVLastPassImporter, JSONImporter, SQLiteTableImporter]
EXPORTERS = [YAMLExporter, PassCodeExporter]


class Transform:
    """Pick an importer and exporter and move data between them."""

    def __init__(self, importer_args: dict | None = None, exporter_args: dict | None = None) -> None:
        self.importer_args = importer_args
        self.exporter_args = exporter_args

    def _pick(self, plugins, args, kind: str):
        chosen = None
        for cls in plugins:
            plugin = cls()
            if plugin.is_accepted(args):
                if chosen is not None:
                    raise RuntimeError(
                        f"More than one {kind} for {json.dumps(args, default=str)}"
                    )
                chosen = plugin
        if chosen is None:
            raise RuntimeError(
                f"No {kind}s can handle args: {json.dumps(args, default=str)}"
            )
        return chosen

    @property
    def importer(self):
        return self._pick(IMPORTERS, self.importer_args, "importer")

    @property
    def exporter(self):
        return self._pick(EXPORTERS, self.exporter_args, "exporter")

    def transform(self, importer_args: dict | None = None, exporter_args: dict | None = None) -> Any:
        """Import from ``importer_args`` then export to ``exporter_args``."""
        if not isinstance(importer_args, dict):
            if not self.importer_args:
                raise ValueError(f"Missing importer_args {importer_args}")
        else:
            self.importer_args = importer_args

        if not isinstance(exporter_args, dict):
            if not self.exporter_args:
                raise ValueError(f"Missing exporter_args {exporter_args}")
        else:
            self.exporter_args = exporter_args

        data = self.importer.importx(self.importer_args)
        return self.exporter.export(self.exporter_args, data)
