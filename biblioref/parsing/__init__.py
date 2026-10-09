"""Downstream bibliographic metadata parsing.

Parsing is intentionally separated from PDF reference segmentation so parser
rules can evolve without changing validated extraction boundaries.
"""
from .parser import (
    PARSER_SCHEMA_VERSION,
    PARSER_STATUS,
    PARSER_VERSION,
    flatten_parsed,
    parse_records,
    parse_reference,
)
from .v12_8 import parse_reference as parse_reference_v12_8
from .v12_7 import parse_reference as parse_reference_v12_7
from .v12_6 import parse_reference as parse_reference_v12_6
from .v12_5 import parse_reference as parse_reference_v12_5
from .v12_4 import parse_reference as parse_reference_v12_4
from .v12_3 import parse_reference as parse_reference_v12_3
from .v12_2 import parse_reference as parse_reference_v12_2
from .v12_1 import parse_reference as parse_reference_v12_1
from .v12 import parse_reference as parse_reference_v12
from .v11 import parse_reference as parse_reference_v11
from .v10 import parse_reference as parse_reference_v10
from .v09 import parse_reference as parse_reference_v09
from .v08 import parse_reference as parse_reference_v08
from .v07 import parse_reference as parse_reference_v07
from .v06 import parse_reference as parse_reference_v06
from .v05 import parse_reference as parse_reference_v05
from .v04 import parse_reference as parse_reference_v04
from .v03 import parse_reference as parse_reference_v03
from .v02 import parse_reference as parse_reference_v02
from .legacy import parse_reference as parse_reference_v01
from .legacy import parse_reference_legacy

__all__ = [
    "PARSER_SCHEMA_VERSION",
    "PARSER_STATUS",
    "PARSER_VERSION",
    "flatten_parsed",
    "parse_records",
    "parse_reference",
    "parse_reference_v12_8",
    "parse_reference_v12_7",
    "parse_reference_v12_6",
    "parse_reference_v12_5",
    "parse_reference_v12_4",
    "parse_reference_v12_3",
    "parse_reference_v12_2",
    "parse_reference_v12_1",
    "parse_reference_v12",
    "parse_reference_v11",
    "parse_reference_v10",
    "parse_reference_v09",
    "parse_reference_v08",
    "parse_reference_v07",
    "parse_reference_v06",
    "parse_reference_v05",
    "parse_reference_v04",
    "parse_reference_v03",
    "parse_reference_v02",
    "parse_reference_v01",
    "parse_reference_legacy",
]
