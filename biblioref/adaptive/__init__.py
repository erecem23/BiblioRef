"""Interpretable adaptive analysis used only in non-destructive shadow mode."""

from biblioref.adaptive.annotations import (
    build_boundary_training_rows,
    write_boundary_training_csv,
)
from biblioref.adaptive.discovery import (
    build_shadow_zone_from_region,
    discover_shadow_regions,
)
from biblioref.adaptive.hypotheses import (
    build_adaptive_shadow_report,
    build_discovered_shadow_report,
)
from biblioref.adaptive.scoring import collect_boundary_candidates, score_boundary
from biblioref.adaptive.verification import verify_discovered_region

__all__ = [
    "build_boundary_training_rows",
    "write_boundary_training_csv",
    "build_shadow_zone_from_region",
    "discover_shadow_regions",
    "build_adaptive_shadow_report",
    "build_discovered_shadow_report",
    "collect_boundary_candidates",
    "score_boundary",
    "verify_discovered_region",
]

# v0.8.3 adds document-context and relative-geometry shadow diagnostics.

# v0.9.0 experimental two-pass diagnostics are available from
# biblioref.adaptive.two_pass without changing effective extraction.
