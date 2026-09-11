"""Backward-compatible wrapper for rpg_common.yaml_walk.

This module re-exports ``yaml_walk`` as an alias for
``rpg_common.yaml_walk.get_tablename_keys_data`` so that existing code
that does ``from utilities_perl.rpg_common import yaml_walk`` keeps working.
"""

from rpg_common.yaml_walk import get_tablename_keys_data as yaml_walk

__all__ = ["yaml_walk"]
