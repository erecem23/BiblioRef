# -*- coding: utf-8 -*-
"""Install the cover/front-matter metadata layer on the BiblioRef application.

The detector is downstream from bibliography extraction/parsing. Metadata
ownership remains separate from reference parsing and human edits are preserved.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import threading
import time
from typing import Any

from .cover_v05 import COVER_METADATA_VERSION, _fold, detect_cover_metadata
from biblioref.document_title_v24 import (
    TITLE_READING_REVISION,
    detect_thesis_title,
    title_conflicts_with_people,
)
from biblioref.ocr import OCR_SCAN_REVISION, scan_ocr_needs
from biblioref.ocr_jobs import ocr_need
from .inference import inference_of, install_inference, public_inference
from biblioref.review_problems import problem_counts

APP_METADATA_VERSION = f"2.7.4-{COVER_METADATA_VERSION}-{TITLE_READING_REVISION}"
_METADATA_KEYS = (
    "author", "year", "university", "faculty", "program", "degree_level",
    "director", "codirector", "institution",
)
_TITLE_REVIEW_REASONS = {"title_ambiguous", "title_low_confidence"}
_EXTRA_HUMAN_FIELDS = {"director", "codirector", "institution"}
_TITLE_PERSON_FIELDS = ("author", "director", "codirector")


def _norm(value: Any) -> str:
    import re
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _known_title_people(detected: dict[str, Any]) -> list[str]:
    meta = detected.get("metadata") or {}
    return [
        _norm(meta.get(key))
        for key in _TITLE_PERSON_FIELDS
        if _norm(meta.get(key))
    ]


def _combined_detection(path: Path, filename: str, title_result=None) -> dict[str, Any]:
    """Overlay the validated title suggestion on front-matter metadata."""
    detected = detect_cover_metadata(path, filename)
    known_people = _known_title_people(detected)

    if title_result is None:
        title, title_source = detect_thesis_title(
            path, filename, excluded_people=known_people
        )
    else:
        title, title_source = title_result
        # Imports normally reuse the title already read by original_create. Only
        # the suspicious case pays for another title pass.
        if title_conflicts_with_people(title, known_people):
            title, title_source = detect_thesis_title(
                path, filename, excluded_people=known_people
            )

    title = _norm(title)
    if title:
        detected["title"] = title
        detected["title_source"] = title_source
        detected.setdefault("sources", {})["title"] = title_source
        detected.setdefault("confidence", {})["title"] = {
            "cover_layout": 0.95,
            "pdf_metadata": 0.90,
            "filename": 0.35,
        }.get(title_source, 0.50)

    candidates = detected.setdefault("candidates", {})
    candidates.pop("title", None)
    reasons = [
        reason for reason in (detected.get("review_reasons") or [])
        if reason not in _TITLE_REVIEW_REASONS
    ]
    if title_source == "filename":
        reasons.append("title_low_confidence")
    detected["review_reasons"] = list(dict.fromkeys(reasons))
    detected["needs_review"] = bool(detected["review_reasons"])
    detected["title_revision"] = TITLE_READING_REVISION
    try:
        # Only records which pages are images without text; OCR itself is a later, explicit step.
        detected["ocr_scan"] = scan_ocr_needs(path)
    except Exception:
        pass
    return detected


def _detection_public(detected: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": detected.get("version") or COVER_METADATA_VERSION,
        "title_revision": detected.get("title_revision") or TITLE_READING_REVISION,
        "sources": deepcopy(detected.get("sources") or {}),
        "confidence": deepcopy(detected.get("confidence") or {}),
        "suggestions": deepcopy(detected.get("metadata") or {}),
        "needs_review": bool(detected.get("needs_review")),
        "review_reasons": deepcopy(detected.get("review_reasons") or []),
        "candidates": deepcopy(detected.get("candidates") or {}),
    }


def _previous_auto_suggestions(doc: dict[str, Any]) -> dict[str, Any]:
    detection = doc.get("metadata_detection")
    if not isinstance(detection, dict):
        return {}
    suggestions = detection.get("suggestions")
    return suggestions if isinstance(suggestions, dict) else {}


def _may_refresh_auto_value(current: Any, previous_suggestion: Any) -> bool:
    """Refresh only empty values or values traceable to the previous detector."""
    cur = _norm(current)
    if not cur:
        return True
    prev = _norm(previous_suggestion)
    return bool(prev and cur == prev)


def _apply_cover_metadata(
    app_module,
    doc: dict[str, Any],
    *,
    allow_title_update: bool = True,
    allow_metadata_update: bool = True,
    title_result=None,
    detected: dict[str, Any] | None = None,
) -> bool:
    path = Path(doc.get("path") or "")
    if not path.exists():
        return False
    filename = str(doc.get("filename") or path.name)
    if detected is None:
        detected = (
            _combined_detection(path, filename)
            if title_result is None
            else _combined_detection(path, filename, title_result=title_result)
        )
    changed = False

    title_source = _norm(doc.get("title_source") or "").casefold()
    title_is_human = bool(doc.get("title_confirmed")) or title_source == "human"
    if allow_title_update and not title_is_human:
        title = _norm(detected.get("title") or "")
        if title and title != _norm(doc.get("title") or ""):
            doc["title"] = title
            doc["title_source"] = detected.get("title_source") or "cover_layout"
            changed = True

    meta = doc.setdefault("metadata", {})
    if not isinstance(meta, dict):
        meta = {}
        doc["metadata"] = meta
        changed = True

    if allow_metadata_update:
        previous = _previous_auto_suggestions(doc)
        suggestions = detected.get("metadata") or {}
        for key in _METADATA_KEYS:
            value = _norm(suggestions.get(key) or "")
            current = meta.get(key)
            if inference_of(doc, key):
                if value:
                    # The PDF now states it: a read value replaces the inference.
                    doc["metadata_inference"].pop(key, None)
                    meta[key] = value
                    changed = True
                continue
            if not value:
                # The new reading no longer supports the previous automatic
                # value (a label, acknowledgement or body fragment): drop it,
                # unless a person has edited the field since.
                prev = _norm(previous.get(key))
                if prev and _norm(current) == prev:
                    meta.pop(key, None)
                    changed = True
                continue
            if _may_refresh_auto_value(current, previous.get(key)):
                # A reading that only loses accents ("Psicologia") keeps the accented value.
                if _fold(value) != _fold(_norm(current)):
                    meta[key] = value
                    changed = True

    public_detection = _detection_public(detected)
    if doc.get("metadata_detection") != public_detection:
        doc["metadata_detection"] = public_detection
        changed = True
    if doc.get("cover_metadata_revision") != COVER_METADATA_VERSION:
        doc["cover_metadata_revision"] = COVER_METADATA_VERSION
        changed = True
    if doc.get("title_reading_revision") != TITLE_READING_REVISION:
        doc["title_reading_revision"] = TITLE_READING_REVISION
        changed = True
    if detected.get("ocr_scan") and doc.get("ocr_scan") != detected["ocr_scan"]:
        doc["ocr_scan"] = detected["ocr_scan"]
        changed = True
    return changed


def _is_stale(doc: dict[str, Any]) -> bool:
    return (
        doc.get("cover_metadata_revision") != COVER_METADATA_VERSION
        or doc.get("title_reading_revision") != TITLE_READING_REVISION
        or (doc.get("ocr_scan") or {}).get("revision") != OCR_SCAN_REVISION
    )


def _refresh_detection(path: str, filename: str) -> dict[str, Any]:
    """Worker-process task: read one thesis front matter; never touches the store."""
    return _combined_detection(Path(path), filename)


# Background re-reading of theses stored with an older detector revision.
# Opening a project stays an index read; the PDFs are re-read in the shared
# pdf_workers processes and results are applied (and saved) in batches here.
_REFRESH_LOCK = threading.Lock()
_REFRESH: dict[str, dict[str, Any]] = {}
_REFRESH_SAVE_EVERY = 40
_REFRESH_SAVE_SECONDS = 30.0


def _refresh_status(project_id: str) -> dict[str, Any]:
    with _REFRESH_LOCK:
        return dict(_REFRESH.get(project_id) or {"running": False, "done": 0, "total": 0, "failed": 0})


def _start_refresh(app_module, project_id: str) -> dict[str, Any]:
    """Start re-reading the project's stale theses unless a run is active."""
    store = app_module.STORE
    with _REFRESH_LOCK:
        current = _REFRESH.get(project_id)
        if current and current.get("running"):
            return dict(current)
        with store.lock:
            ids = [
                doc_id for doc_id, doc in store.docs().items()
                if doc.get("project_id") == project_id and _is_stale(doc)
                and Path(doc.get("path") or "").exists()
            ]
        state = {"running": bool(ids), "done": 0, "total": len(ids), "failed": 0}
        _REFRESH[project_id] = state
    if ids:
        threading.Thread(
            target=_run_refresh, args=(app_module, ids, state),
            name="frontmatter-refresh", daemon=True,
        ).start()
    return dict(state)


def _run_refresh(app_module, ids: list[str], state: dict[str, Any]) -> None:
    from concurrent.futures import FIRST_COMPLETED, wait
    from concurrent.futures.process import BrokenProcessPool
    from biblioref.pdf_workers import discard_broken_pool, get_pool, worker_count

    store = app_module.STORE
    todo = iter(ids)
    pending: dict[Any, str] = {}
    unsaved, last_save = 0, time.monotonic()
    pool = None
    try:
        pool = get_pool()
        while True:
            while len(pending) < 2 * worker_count():
                doc_id = next(todo, None)
                if doc_id is None:
                    break
                with store.lock:
                    doc = store.docs().get(doc_id)
                    job = None
                    if doc is not None and _is_stale(doc):
                        path = str(doc.get("path") or "")
                        job = (path, str(doc.get("filename") or Path(path).name))
                if job is None:  # deleted, or refreshed meanwhile by opening it
                    state["done"] += 1
                    continue
                pending[pool.submit(_refresh_detection, *job)] = doc_id
            if not pending:
                break
            finished, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in finished:
                doc_id = pending.pop(future)
                try:
                    detected = future.result()
                except BrokenProcessPool:
                    raise
                except Exception:
                    state["failed"] += 1
                else:
                    with store.lock:
                        doc = store.docs().get(doc_id)
                        if doc is not None and _is_stale(doc):
                            cover_stale = doc.get("cover_metadata_revision") != COVER_METADATA_VERSION
                            _apply_cover_metadata(
                                app_module, doc, allow_metadata_update=cover_stale, detected=detected,
                            )
                            unsaved += 1
                state["done"] += 1
            if unsaved and (unsaved >= _REFRESH_SAVE_EVERY or time.monotonic() - last_save >= _REFRESH_SAVE_SECONDS):
                store.save()
                unsaved, last_save = 0, time.monotonic()
    except BrokenProcessPool:
        if pool is not None:
            discard_broken_pool(pool)
        state["error"] = "Se interrumpió uno de los procesos de lectura."
    except Exception as exc:  # keep the app alive; the status route reports it
        state["error"] = str(exc)
    finally:
        if unsaved:
            try:
                store.save()
            except Exception as exc:
                state["error"] = str(exc)
        state["running"] = False


def install_cover_metadata(app_module) -> None:
    """Install cover metadata and document-title detection exactly once."""
    app = app_module.app
    if getattr(app.state, "cover_metadata_installed", False):
        return
    app.state.cover_metadata_installed = True
    app_module.TITLE_IDENTITY_REVISION = TITLE_READING_REVISION

    original_detect_title = app_module._detect_thesis_title
    original_ensure = app_module._ensure_doc_identity
    original_create = app_module._create_document_from_pdf_path
    original_public_doc = app_module._public_doc

    def detect_title(path, filename):
        title, source = detect_thesis_title(Path(path), str(filename))
        title = _norm(title)
        if title:
            return title, source
        return original_detect_title(path, filename)

    def ensure_doc_identity(doc: dict[str, Any]) -> bool:
        cover_stale = doc.get("cover_metadata_revision") != COVER_METADATA_VERSION
        title_stale = doc.get("title_reading_revision") != TITLE_READING_REVISION
        changed = bool(original_ensure(doc))
        if _is_stale(doc):
            changed = _apply_cover_metadata(
                app_module,
                doc,
                allow_title_update=title_stale or cover_stale,
                allow_metadata_update=cover_stale,
            ) or changed
        return changed

    def create_document_from_pdf_path(source_path, filename, ingestion=None):
        doc = original_create(source_path, filename, ingestion)
        _apply_cover_metadata(
            app_module,
            doc,
            allow_title_update=True,
            allow_metadata_update=True,
            title_result=(doc["title"], doc["title_source"]),
        )
        return doc

    def public_doc(doc: dict[str, Any], include_refs: bool = False):
        out = original_public_doc(doc, include_refs)
        if doc.get("metadata_detection") is not None:
            out["metadata_detection"] = deepcopy(doc.get("metadata_detection"))
        if doc.get("cover_metadata_revision") is not None:
            out["cover_metadata_revision"] = doc.get("cover_metadata_revision")
        if doc.get("title_reading_revision") is not None:
            out["title_reading_revision"] = doc.get("title_reading_revision")
        out["frontmatter_refresh_pending"] = _is_stale(doc)
        out["ocr_scan"] = deepcopy(doc.get("ocr_scan"))
        out["ocr"] = deepcopy(doc.get("ocr"))
        out["ocr_need"] = ocr_need(doc)
        out["metadata_inference"] = public_inference(doc)
        out["problems"] = problem_counts(doc)
        out["discarded_sections"] = deepcopy(doc.get("discarded_sections") or [])
        return out

    @app.get("/api/projects/{project_id}/documents-index")
    def project_documents_index(project_id: str):
        """Return stored summaries without reopening every PDF.

        Theses read with an older detector are re-read in the background; the
        index only reports the progress of that run.
        """
        app_module._ensure_projects()
        app_module._get_project(project_id)
        docs = sorted(app_module.STORE.docs().values(), key=lambda d: d.get("created_at", 0))
        docs = [d for d in docs if d.get("project_id") == project_id]
        # Theses processed before the wider merged-reference rule get it once, without reprocessing.
        from biblioref.audit.merged import backfill_merged_suspects
        with app_module.STORE.lock:
            if sum([backfill_merged_suspects(d) for d in docs]):
                app_module.STORE.save()
        pending = sum(1 for d in docs if _is_stale(d))
        return {
            "documents": [app_module._public_doc(d, False) for d in docs],
            "frontmatter_refresh_pending": pending,
            "frontmatter_refresh": _start_refresh(app_module, project_id) if pending else _refresh_status(project_id),
        }

    @app.get("/api/projects/{project_id}/frontmatter-refresh")
    def frontmatter_refresh_status(project_id: str):
        app_module._get_project(project_id)
        return _refresh_status(project_id)

    @app.patch("/api/documents/{doc_id}/frontmatter-metadata")
    def update_frontmatter_metadata(doc_id: str, payload: dict[str, Any]):
        """Edit captured front-matter fields without changing bibliography state."""
        doc = app_module.STORE.get(doc_id)
        meta = doc.setdefault("metadata", {})
        changes: dict[str, Any] = {}
        for key in _EXTRA_HUMAN_FIELDS:
            if key not in payload:
                continue
            value = _norm(payload.get(key))[:500]
            before = meta.get(key)
            if value:
                meta[key] = value
            else:
                meta.pop(key, None)
            if value != _norm(before):
                changes[key] = {"before": before, "after": value or None}
        if changes:
            doc["updated_at"] = app_module._now()
            app_module._log_correction(doc, "edit_frontmatter_metadata", {"changes": changes})
            app_module.STORE.save()
        return app_module._public_doc(doc, True)

    app_module._detect_thesis_title = detect_title
    app_module._ensure_doc_identity = ensure_doc_identity
    app_module._create_document_from_pdf_path = create_document_from_pdf_path
    app_module._public_doc = public_doc

    from biblioref.ocr_jobs import install_ocr
    install_ocr(app_module, reread=lambda doc: _apply_cover_metadata(app_module, doc))
    install_inference(app_module)

    from biblioref.project_organize import install_project_organize
    install_project_organize(app_module)
    app_module.APP_VERSION = "2.7.4"
