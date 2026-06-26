"""utilities-perl-py — Python port of the Perl ``utilities-perl`` repo.

A small collection of home-made utility libraries and CLI scripts, ported from
Perl to Python. See ``README.md`` for the full Perl -> Python module mapping.
"""

from .alert import Alert
from .ask import ask
from .config import GetCommonConfig
from .csv_lastpass import CSVLastPass
from .email_to_hash import EmailToHash
from .passcode import PassCode, PassCodeFile
from .prettyprint import (
    data_to_json_pretty,
    print_arrays,
    print_hashes,
    set_array_item,
)
from .transform import Transform

__version__ = "0.1.0"

__all__ = [
    "Alert",
    "ask",
    "GetCommonConfig",
    "CSVLastPass",
    "EmailToHash",
    "PassCode",
    "PassCodeFile",
    "Transform",
    "data_to_json_pretty",
    "print_arrays",
    "print_hashes",
    "set_array_item",
    "__version__",
]
