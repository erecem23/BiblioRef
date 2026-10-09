"""Runtime selection for BiblioRef's PDF backend.

PyMuPDF remains the stable/default backend while it is installed.  In a
PyMuPDF-free installation the same narrow document API is provided by PDFium.
The explicit context manager is used by differential validation so every
downstream helper observes the same backend without global monkeypatching.
"""
from __future__ import annotations

import importlib
import os
from contextlib import contextmanager
from contextvars import ContextVar
from importlib.util import find_spec
from typing import Iterator


PDF_BACKENDS = ("pymupdf", "pdfium")
_BACKEND_OVERRIDE: ContextVar[str | None] = ContextVar(
    "biblioref_pdf_backend", default=None
)


def _module_available(name: str) -> bool:
    try:
        return find_spec(name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def pymupdf_available() -> bool:
    return _module_available("pymupdf")


def pdfium_available() -> bool:
    return _module_available("pypdfium2")


def active_pdf_backend() -> str:
    """Return the explicit backend or the safest installed default."""
    selected = _BACKEND_OVERRIDE.get()
    if selected is None:
        configured = os.environ.get("BIBLIOREF_PDF_BACKEND", "").strip().lower()
        selected = configured or None
    if selected is not None:
        if selected not in PDF_BACKENDS:
            raise ValueError(
                f"Unsupported PDF backend {selected!r}; choose one of {PDF_BACKENDS}"
            )
        return selected
    if pymupdf_available():
        return "pymupdf"
    if pdfium_available():
        return "pdfium"
    raise RuntimeError("No supported PDF backend is installed")


@contextmanager
def use_pdf_backend(name: str) -> Iterator[str]:
    """Temporarily select one backend for the complete call graph."""
    normalized = str(name).strip().lower()
    if normalized not in PDF_BACKENDS:
        raise ValueError(
            f"Unsupported PDF backend {name!r}; choose one of {PDF_BACKENDS}"
        )
    if normalized == "pymupdf" and not pymupdf_available():
        raise ModuleNotFoundError("PyMuPDF is not installed")
    if normalized == "pdfium" and not pdfium_available():
        raise ModuleNotFoundError("pypdfium2 is not installed")
    token = _BACKEND_OVERRIDE.set(normalized)
    try:
        yield normalized
    finally:
        _BACKEND_OVERRIDE.reset(token)


def available_pdf_backends() -> tuple[str, ...]:
    values = []
    if pymupdf_available():
        values.append("pymupdf")
    if pdfium_available():
        values.append("pdfium")
    return tuple(values)


def _pymupdf_module():
    try:
        return importlib.import_module("pymupdf")
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "PyMuPDF is not installed; select the PDFium backend or install PyMuPDF"
        ) from exc


class _BackendModuleProxy:
    """Small ``pymupdf``-shaped proxy used by legacy PDF call sites.

    Defining ``open`` and ``Matrix`` as ordinary instance methods preserves
    compatibility with tests that patch ``biblioref_v0_3.pymupdf.open``.
    """

    def open(self, *args, **kwargs):
        if active_pdf_backend() == "pymupdf":
            return _pymupdf_module().open(*args, **kwargs)
        from biblioref.ingestion.pdfium_primitives import open_pdfium_document

        return open_pdfium_document(*args, **kwargs)

    def Matrix(self, x: float, y: float | None = None):  # noqa: N802 - API parity
        if active_pdf_backend() == "pymupdf":
            return _pymupdf_module().Matrix(x, x if y is None else y)
        from biblioref.ingestion.pdfium_primitives import PdfiumMatrix

        return PdfiumMatrix(float(x), float(x if y is None else y))

    def __getattr__(self, name: str):
        if active_pdf_backend() != "pymupdf":
            raise AttributeError(
                f"The PDFium compatibility surface does not expose {name!r}"
            )
        return getattr(_pymupdf_module(), name)


pymupdf = _BackendModuleProxy()


__all__ = [
    "PDF_BACKENDS",
    "active_pdf_backend",
    "available_pdf_backends",
    "pdfium_available",
    "pymupdf",
    "pymupdf_available",
    "use_pdf_backend",
]
