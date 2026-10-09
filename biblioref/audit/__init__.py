"""Public API for the optional visual-audit layer.

Exports are loaded lazily so importing the extraction core does not require
pandas, openpyxl or Streamlit.
"""

from importlib import import_module

from biblioref.core.config import AUDIT_APP_VERSION


_LAZY_EXPORTS = {
    "ManualZoneSpec": ("biblioref.audit.models", "ManualZoneSpec"),
    "candidate_heading_lines": ("biblioref.audit.detection", "candidate_heading_lines"),
    "detect_reference_like_regions": (
        "biblioref.audit.detection",
        "detect_reference_like_regions",
    ),
    "nearest_line": ("biblioref.audit.detection", "nearest_line"),
    "process_manual_zone": ("biblioref.audit.manual", "process_manual_zone"),
    "add_audit_columns": ("biblioref.audit.export", "add_audit_columns"),
    "build_audit_bundle": ("biblioref.audit.export", "build_audit_bundle"),
    "dataframe_csv_bytes": ("biblioref.audit.export", "dataframe_csv_bytes"),
    "workbook_bytes": ("biblioref.audit.export", "workbook_bytes"),
    "resolution_audit_columns": ("biblioref.audit.resolution", "resolution_audit_columns"),
    "attach_resolution_columns": ("biblioref.audit.resolution", "attach_resolution_columns"),
    "page_dimensions": ("biblioref.ingestion", "page_dimensions"),
    "pdf_page_count": ("biblioref.ingestion", "pdf_page_count"),
    "render_page_png": ("biblioref.ingestion", "render_page_png"),
    "analyze_surveillance": ("biblioref.audit.surveillance", "analyze_surveillance"),
}


def __getattr__(name: str):
    try:
        module_name, attribute = _LAZY_EXPORTS[name]
    except KeyError as error:
        raise AttributeError(name) from error
    value = getattr(import_module(module_name), attribute)
    globals()[name] = value
    return value


def __dir__():
    return sorted({*globals(), *_LAZY_EXPORTS})


__all__ = ["AUDIT_APP_VERSION", *_LAZY_EXPORTS]
