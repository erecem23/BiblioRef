"""Process-wide lock for PDFium calls.

PDFium is not thread-safe: two threads calling into it at the same time corrupt
its global state, and every later call in the process then fails with
"Failed to load document (PDFium: Data format error)". The command line runs in
one thread, but the local application serves page images and analyses from a
thread pool. Every pypdfium2 call in BiblioRef goes through this lock, so calls
from different threads are serialized. It is reentrant because document,
page and text-page operations nest.
"""
from __future__ import annotations

import threading

PDFIUM_LOCK = threading.RLock()

__all__ = ["PDFIUM_LOCK"]
