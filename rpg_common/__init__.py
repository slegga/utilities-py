"""rpg_common -- felles Python-logikk for mm-rpg og osr-rpg.

Pakken samler Jinja2-baserte templatehjelpere og en rekursiv
YAML-til-tabell-konvertering som er portert fra Perl.

Brukseksempel::

    from rpg_common import ctable, clist, mytextsort, gterning
    from rpg_common import get_tablename_keys_data, load_rekkefoelge
"""

from .template import (
    clist,
    ctable,
    gterning,
    load_rekkefoelge,
    myrowsort,
    mytextsort,
)
from .yaml_walk import get_tablename_keys_data

__all__ = [
    "clist",
    "ctable",
    "get_tablename_keys_data",
    "gterning",
    "load_rekkefoelge",
    "myrowsort",
    "mytextsort",
]
