"""Best-effort thesis/document metadata detection."""

from .cover_v05 import COVER_METADATA_VERSION, detect_cover_metadata

__all__ = ["COVER_METADATA_VERSION", "detect_cover_metadata"]
