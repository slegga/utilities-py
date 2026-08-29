"""Recursive walker for relational schema extraction from nested YAML data.

Port of ``SH::Mmradio::SchemaWalker`` from Perl to Python.  Takes a nested
data structure of dicts, lists and scalars (as loaded from YAML episode files
under ``analyse-radio/``) and projects it onto a relational shape suitable
for SQLite import.

The projected shape is a dict of tables::

    return = {
        'tablename': {
            'fields': ['id', 'id_root', 'col1', 'col2', ...],
            'data': [
                {'id': 0, 'id_root': 1, 'col1': ..., 'col2': ...},
                ...
            ],
        },
        ...
    }

Nesting is resolved by materialising a new table per nested dict or per
list-of-dicts, joined back to the parent by ``id_<parent_tablename>``.
"""

from __future__ import annotations

from typing import Any


def yaml_walk(
    tablename: str,
    ret: dict[str, Any],
    data: Any,
    fk_name: str = "root",
    fk_id: int = 1,
) -> None:
    """Build a relational projection of *data* rooted at *tablename*.

    Mutates *ret* in place, accumulating table definitions, field lists
    and row data.

    Parameters
    ----------
    tablename:
        Name of the table to start from.
    ret:
        Dict that accumulates tables/fields/data.  Must be a dict.
    data:
        The input data structure (dict, list-of-dicts, or list-of-scalars).
    fk_name:
        Name of the parent table used to build the foreign-key column
        ``id_<fk_name>`` on the current table.
    fk_id:
        Numeric id of the parent row.

    Raises
    ------
    TypeError
        If *ret* is not a dict or *data* has an unsupported type.
    """
    if not isinstance(ret, dict):
        raise TypeError("$return is not a HASH")

    # Determine the next row id for this table.
    table = ret.setdefault(tablename, {"fields": [], "data": []})
    row_id = len(table["data"])

    if isinstance(data, dict):
        _walk_dict(tablename, ret, data, row_id, fk_name, fk_id)
    elif isinstance(data, list):
        _walk_list(tablename, ret, data, fk_name, fk_id)
    else:
        raise TypeError(f"Unsupported data ref: {type(data).__name__ or 'not a ref'}")


def _ensure_field(table: dict[str, Any], field: str) -> None:
    """Add *field* to the table's field list if not already present."""
    if field not in table["fields"]:
        table["fields"].append(field)


def _walk_dict(
    tablename: str,
    ret: dict[str, Any],
    data: dict[str, Any],
    row_id: int,
    fk_name: str,
    fk_id: int,
) -> None:
    table = ret[tablename]

    # Ensure id and foreign-key fields exist.
    _ensure_field(table, "id")
    table["data"].append({"id": row_id})

    _ensure_field(table, f"id_{fk_name}")
    table["data"][row_id][f"id_{fk_name}"] = fk_id

    for key, value in data.items():
        if not isinstance(value, (dict, list)):
            # Scalar value.
            _ensure_field(table, key)
            table["data"][row_id][key] = value
        elif isinstance(value, dict):
            yaml_walk(key, ret, value, tablename, row_id)
        elif isinstance(value, list):
            if value and isinstance(value[0], dict):
                yaml_walk(key, ret, value, tablename, row_id)
            elif value and not isinstance(value[0], (dict, list)):
                # Array of scalars: comma-join into one field.
                _ensure_field(table, key)
                joined = ",".join(str(v) for v in value)
                table["data"][row_id][key] = joined
            else:
                raise TypeError(
                    f"Unsupported ARRAY value at key '{key}': "
                    f"ARRAY-of-{type(value[0]).__name__ if value else 'empty'}"
                )


def _walk_list(
    tablename: str,
    ret: dict[str, Any],
    data: list[Any],
    fk_name: str,
    fk_id: int,
) -> None:
    if not data:
        return
    first = data[0]
    if isinstance(first, dict):
        for element in data:
            yaml_walk(tablename, ret, element, fk_name, fk_id)
    elif not isinstance(first, (dict, list)):
        # Top-level list of scalars: no-op (matches Perl behaviour).
        return
    else:
        raise TypeError(
            f"Unsupported top-level ARRAY: ARRAY-of-{type(first).__name__}"
        )
