"""Compact catalog of grammar capabilities represented by v0.8.5-a."""

SUPPORTED_GRAMMAR_CONCEPTS = {
    "author_year_parenthetical",
    "author_year_bare",
    "year_only_inherited_author",
    "repeated_author_marker",
    "numeric_marker",
    "marker_only_numeric",
    "numeric_prefix_marker",
    "numeric_comma_marker",
    "bracket_key_marker",
    "institutional_author",
    "institutional_author_late_date",
    "standard_document_start",
    "undated_author",
    "dot_initial_author",
    "title_only_successor",
    "wrapped_author_list",
    "conference_event_continuation",
}

SUPPORTED_REGIMES = {"numeric", "bracket_key", "alphabetical", "mixed", "unknown"}

__all__ = ["SUPPORTED_GRAMMAR_CONCEPTS", "SUPPORTED_REGIMES"]
