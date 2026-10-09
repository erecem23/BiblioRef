# -*- coding: utf-8 -*-
"""Public API for the modular BiblioRef package (lazy pipeline)."""

from biblioref.core.config import SOFTWARE_VERSION
__all__ = ["SOFTWARE_VERSION", "process_pdf"]
__version__ = SOFTWARE_VERSION


def __getattr__(name: str):
    if name == "process_pdf":
        from biblioref.pipeline import process_pdf
        return process_pdf
    raise AttributeError(name)
