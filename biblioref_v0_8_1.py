# -*- coding: utf-8 -*-
"""Compatibility entry point for BiblioRef v0.8.1 adaptive shadow."""

from biblioref.core.config import SOFTWARE_VERSION
from biblioref.interfaces.cli import main
from biblioref.pipeline import process_pdf

__all__ = ["SOFTWARE_VERSION", "process_pdf", "main"]

if __name__ == "__main__":
    raise SystemExit(main())
