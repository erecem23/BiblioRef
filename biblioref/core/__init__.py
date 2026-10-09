"""Shared configuration and types used by the extraction pipeline."""

from biblioref.core.config import (
    ALGORITHM_VERSION,
    AUDIT_APP_VERSION,
    BASE_VERSION,
    SOFTWARE_VERSION,
    STABLE_ENGINE_VERSION,
)
from biblioref.core.types import Report, Scope

__all__ = [
    "ALGORITHM_VERSION",
    "AUDIT_APP_VERSION",
    "BASE_VERSION",
    "Report",
    "SOFTWARE_VERSION",
    "STABLE_ENGINE_VERSION",
    "Scope",
]
