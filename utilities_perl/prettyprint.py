"""Pretty printing helpers.

Python port of the Perl ``SH::PrettyPrint`` module: a small collection of
functions for printing tabular data and producing ordered, pretty JSON.
"""

from __future__ import annotations

import copy
import json
from typing import Any, Mapping, MutableSequence, Sequence


def print_arrays(rows: Sequence[Sequence[Any]]) -> str:
    """Render an array of arrays with tab separators.

    Mirrors ``SH::PrettyPrint::print_arrays`` which printed each row joined by
    a tab. This returns the rendered string (the Perl version printed directly).
    """
    return "".join("\t".join(str(c) for c in row) + "\n" for row in rows)


def print_hashes(rows: Sequence[Mapping[str, Any]], options: Mapping[str, Any] | None = None) -> str:
    """Render an array of dicts as an aligned table with a header row.

    ``options['columns']`` may give a list of columns that should appear first.
    """
    if not rows:
        return ""
    keys = sorted(rows[0].keys())

    if options and "columns" in options:
        wanted = list(options["columns"])
        for col in wanted:
            if col in keys:
                keys.remove(col)
        keys = wanted + keys

    size = {key: len(key) for key in keys}
    for row in rows:
        for key in keys:
            if key not in row:
                continue
            value = row[key]
            if value and len(str(value)) > size[key]:
                size[key] = len(str(value))

    out = "".join(f"{key:<{size[key]}} " for key in keys) + "\n"
    for row in rows:
        out += "".join(f"{str(row.get(key, '') if row.get(key) is not None else ''):<{size[key]}} " for key in keys)
        out += "\n"
    return out


def data_to_json_pretty(data: Any, opts: Mapping[str, Any] | None = None) -> str:
    """Produce ordered, pretty-printed JSON.

    ``opts`` keys:
        order       list of keys that should be emitted first (in this order)
        indent_text indentation unit (default a tab)

    When ``opts`` is not a mapping, falls back to a standard pretty dump.
    """
    if not isinstance(opts, Mapping):
        return json.dumps(data, indent=4, ensure_ascii=False)

    new_opts = dict(copy.deepcopy(opts))
    new_opts.setdefault("indent_text", "\t")

    if isinstance(data, dict):
        if isinstance(opts.get("order"), list):
            return _req_value_hash(data, new_opts, 0)
        raise NotImplementedError("data_to_json_pretty without 'order' is not implemented")
    raise NotImplementedError("data_to_json_pretty expects a dict at the top level")


def _req_key_order(data: Mapping[str, Any], opts: Mapping[str, Any]) -> list[str]:
    keys = list(data.keys())
    out: list[str] = []
    for key in [k for k in opts.get("order", []) if k is not None]:
        if key in keys:
            keys.remove(key)
            out.append(key)
    out.extend(sorted(keys))
    return out


def _req_value_hash(data: Mapping[str, Any], opts: Mapping[str, Any], indent: int) -> str:
    indent += 1
    indent_text = opts["indent_text"]
    parts: list[str] = []
    for key in _req_key_order(data, opts):
        value = data[key]
        prefix = indent_text * indent + f'"{key}": '
        if isinstance(value, dict):
            parts.append(prefix + _req_value_hash(value, opts, indent))
        elif isinstance(value, list):
            parts.append(prefix + _req_value_array(value, opts, indent))
        elif isinstance(value, bool):
            parts.append(prefix + ("true" if value else "false"))
        else:
            parts.append(prefix + f'"{value}"')
    indent -= 1
    return "{\n" + ",\n".join(parts) + "\n" + indent_text * indent + "}"


def _req_value_array(data: Sequence[Any], opts: Mapping[str, Any], indent: int) -> str:
    indent += 1
    indent_text = opts["indent_text"]
    parts: list[str] = []
    for item in data:
        prefix = indent_text * indent
        if isinstance(item, dict):
            parts.append(prefix + _req_value_hash(item, opts, indent))
        elif isinstance(item, list):
            raise NotImplementedError("nested arrays are not implemented")
        else:
            parts.append(prefix + f'"{item}"')
    indent -= 1
    return "[\n" + ",\n".join(parts) + "\n" + indent_text * indent + "]"


def set_array_item(array_ref: MutableSequence[Any], *pointer_and_value: Any) -> None:
    """Set a (possibly nested) item inside ``array_ref`` in place.

    The last positional argument is the value, the preceding ones index into the
    list. Port of ``SH::PrettyPrint::_set_array_item`` (supports up to 3 levels).
    """
    if not pointer_and_value:
        raise ValueError("To few values")
    *pointer, value = pointer_and_value
    if value is None:
        raise ValueError("To few values")
    if len(pointer) == 0:
        raise ValueError("No pointer")
    if len(pointer) == 1:
        array_ref[pointer[0]] = value
    elif len(pointer) == 2:
        array_ref[pointer[0]][pointer[1]] = value
    elif len(pointer) == 3:
        array_ref[pointer[0]][pointer[1]][pointer[2]] = value
    else:
        raise ValueError("To many paramters no support")
