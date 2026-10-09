"""Shadow-only bibliographic style profiling for BiblioRef."""
from .features import extract_reference_features
from .profiler import (
    STYLE_PROFILE_SCHEMA_VERSION,
    STYLE_PROFILER_STATUS,
    STYLE_PROFILER_VERSION,
    profile_document,
    profile_references,
)

__all__ = [
    "STYLE_PROFILE_SCHEMA_VERSION",
    "STYLE_PROFILER_STATUS",
    "STYLE_PROFILER_VERSION",
    "extract_reference_features",
    "profile_document",
    "profile_references",
]
