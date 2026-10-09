"""Bounded, reusable PDF processes. Workers never write the project store.

PyMuPDF is not thread-safe. Use spawn on Windows and POSIX, passing paths and
plain results rather than open PDF objects. All writes stay in the parent.
"""
from __future__ import annotations

import atexit
from concurrent.futures import ProcessPoolExecutor
import multiprocessing
import os
import threading
from pathlib import Path

_pool = None
_lock = threading.Lock()


def worker_count():
    cpus = os.cpu_count() or 1
    if hasattr(os, "sched_getaffinity"):
        cpus = min(cpus, len(os.sched_getaffinity(0)))
    default = min(4, max(1, cpus - 1))
    try:
        requested = int(os.environ.get("BIBLIOREF_WORKERS", default))
    except ValueError:
        requested = default
    return max(1, min(requested, cpus, 8))


def get_pool():
    global _pool
    with _lock:
        if _pool is None:
            _pool = ProcessPoolExecutor(max_workers=worker_count(),
                                       mp_context=multiprocessing.get_context("spawn"))
        return _pool


def discard_broken_pool(pool):
    global _pool
    with _lock:
        if _pool is pool:
            _pool = None
    pool.shutdown(wait=False, cancel_futures=True)


def shutdown_pool():
    global _pool
    with _lock:
        pool, _pool = _pool, None
    if pool is not None:
        pool.shutdown(wait=True, cancel_futures=True)


atexit.register(shutdown_pool)


class UnreadablePdf(Exception):
    """One staged PDF could not be read; carries the reason, not the frames."""


def prepare_pdf(path: str, filename: str):
    try:
        return _prepare_pdf(path, filename)
    except Exception as exc:
        reason = str(exc)
    # Raised outside the except block on purpose: the original traceback keeps
    # the failed PDF document alive in this worker, and on Windows that holds
    # the staged file open so the import directory cannot be cleaned up.
    raise UnreadablePdf(reason)


def _prepare_pdf(path: str, filename: str):
    from biblioref.ingestion import pdf_preflight
    from biblioref.document_title import detect_thesis_title, TITLE_READING_REVISION
    from biblioref.metadata.integration import _combined_detection, _detection_public
    from biblioref.metadata.cover import COVER_METADATA_VERSION

    source = Path(path)
    preflight = pdf_preflight(source)
    title, title_source = detect_thesis_title(source, filename)
    detected = _combined_detection(source, filename, title_result=(title, title_source))
    return {
        "preflight": preflight, "title": title, "title_source": title_source,
        "extras": {
            "metadata": detected.get("metadata") or {},
            "metadata_detection": _detection_public(detected),
            "cover_metadata_revision": COVER_METADATA_VERSION,
            "title_reading_revision": TITLE_READING_REVISION,
        },
    }


def analyze_pdf(path: str, rescue_profile: str):
    from biblioref.pipeline import process_pdf
    return process_pdf(Path(path), scope="all_reference_sections", adaptive_mode="shadow",
                       rescue_profile=rescue_profile, rescue_audit=True)
