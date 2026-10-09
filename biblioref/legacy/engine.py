"""Explicit adapter to the validated v0.2-v0.6 engine modules.

Only this module should know where historical implementations live.  New
modules import stable primitives from here, allowing those primitives to move
later without changing the public API or user interfaces.
"""

from biblioref_v0_2 import (
    AUTHOR_COMMA_RX,
    BRACKET_KEY_RX,
    BULLET_RX,
    NUMERIC_MARKER_RX,
    SCOPE_DEFINITIONS,
    VALID_SCOPES,
    _annotate_duplicates,
    _select_scope,
    _strip_heading_prefix,
    is_ref_heading,
)
from biblioref_v0_3 import (
    DOI_URL_AT_START_RX,
    SIN_FECHA_RX,
    YEAR_RX,
    LayoutLine,
    _clean_text,
    _is_footer,
    _is_reference_heading,
    _is_small_font_noise,
    _mode_cluster,
    extract_layout_lines,
    clear_layout_line_cache,
)
from biblioref_v0_4 import (
    AdaptiveLayoutZone,
    INTERNAL_BIBLIOGRAPHY_HEADING_RX,
    _has_bare_author_year,
    _has_early_bibliographic_date,
    _numeric_sequence_diagnostics,
    classify_zone_role,
    detect_adaptive_layout_zones,
    diagnose_adaptive_layout,
    diagnose_adaptive_style,
    process_pdf as process_pdf_stable,
    segment_adaptive_layout_zone,
)

__all__ = [name for name in globals() if not name.startswith("__")]
