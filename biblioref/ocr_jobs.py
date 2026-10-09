# -*- coding: utf-8 -*-
"""Routes and a background queue for running OCR on request.

OCR never runs while importing or re-reading a thesis. A thesis with pages
that are images without text reports them in ``ocr_scan``; OCR runs only when
asked, for one thesis or for every thesis in a project that needs it.
"""
from __future__ import annotations

import queue
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from biblioref.ocr import (
    FRONTMATTER_PAGES, OCR_LANGUAGES, OCR_PLACEMENT_REVISION, _ranges, ocr_available, ocr_pdf_pages, ocr_target_path, scan_ocr_needs,
)

_LOCK = threading.Lock()
_JOBS: Dict[str, Dict[str, Any]] = {}
_QUEUE: "queue.Queue[tuple[str, Optional[List[int]]]]" = queue.Queue()
_WORKER: Optional[threading.Thread] = None


# Cover fields that OCR on a scanned cover can fill; the codirector is optional.
_COVER_FIELDS = ("author", "year", "degree_level", "program", "faculty", "university", "director")


def ocr_need(doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """What OCR would unlock in this thesis, or None.

    Loose scanned pages (figures, annexes) do not count: only a fully scanned
    thesis, a scanned cover with missing metadata, or scanned pages inside a
    detected bibliography section.
    """
    scan = doc.get("ocr_scan") or {}
    pages = [int(p) for p in scan.get("pages") or []]
    if not pages:
        return None
    unreadable = bool(scan.get("unreadable_pages"))
    if scan.get("scanned_document"):
        return {"kind": "document", "pages": pages, "cover_pages": [], "bibliography_pages": [], "unreadable": unreadable}
    meta = doc.get("metadata") or {}
    missing_cover = any(not str(meta.get(k) or "").strip() for k in _COVER_FIELDS)
    cover = [int(p) for p in scan.get("frontmatter_pages") or []] if missing_cover else []
    sections = [
        (int(s.get("start_page") or 0), int(s.get("end_page") or s.get("start_page") or 0))
        for s in doc.get("sections") or []
    ]
    bibliography = [p for p in pages if any(a <= p <= b for a, b in sections)]
    if not cover and not bibliography:
        return None
    kind = "cover_bibliography" if cover and bibliography else "cover" if cover else "bibliography"
    return {"kind": kind, "pages": sorted(set(cover) | set(bibliography)),
            "cover_pages": cover, "bibliography_pages": bibliography, "unreadable": unreadable}


def _pages_for_scope(doc: Dict[str, Any], scope: str) -> List[int]:
    scan = doc.get("ocr_scan") or {}
    pages = [int(p) for p in scan.get("pages") or []]
    if scope == "frontmatter":
        return [p for p in pages if p <= FRONTMATTER_PAGES]
    if scope == "needed":
        return (ocr_need(doc) or {}).get("pages") or []
    return pages


def job_status(doc_id: str) -> Dict[str, Any]:
    with _LOCK:
        return dict(_JOBS.get(doc_id) or {"state": "idle"})


def _enqueue(app_module, reread, doc_id: str, pages: List[int], redo: bool = False) -> Dict[str, Any]:
    global _WORKER
    with _LOCK:
        current = _JOBS.get(doc_id)
        if current and current.get("state") in {"queued", "running", "extracting"}:
            return dict(current)
        state = {"state": "queued", "done": 0, "total": len(pages), "pages": pages, "queued_at": time.time(), "redo": redo}
        _JOBS[doc_id] = state
        _QUEUE.put((doc_id, pages, redo))
        if _WORKER is None or not _WORKER.is_alive():
            _WORKER = threading.Thread(target=_work, args=(app_module, reread), name="ocr-queue", daemon=True)
            _WORKER.start()
        return dict(state)


def _work(app_module, reread: Callable[[Dict[str, Any]], Any]) -> None:
    store = app_module.STORE
    while True:
        doc_id, pages, redo = _QUEUE.get()
        state = _JOBS[doc_id]
        try:
            with store.lock:
                doc = store.docs().get(doc_id)
                # Redoing starts again from the PDF as imported, so earlier OCR text is not stacked.
                source = str((doc.get("original_path") if redo else None) or doc.get("path") or "") if doc else ""
            if not doc or not Path(source).exists():
                raise RuntimeError("La tesis ya no está disponible.")
            state["state"] = "running"
            target = ocr_target_path(source)

            def progress(done: int, total: int) -> None:
                state["done"], state["total"] = done, total

            result = ocr_pdf_pages(source, target, pages, progress=progress)
            scan = scan_ocr_needs(target)
            with store.lock:
                doc = store.docs().get(doc_id)
                if doc is None:
                    target.unlink(missing_ok=True)
                    raise RuntimeError("La tesis se quitó durante el OCR.")
                previous = doc.get("ocr") or {}
                doc.setdefault("original_path", source)
                doc["path"] = str(target)
                done_pages = sorted(set([] if redo else previous.get("pages") or []) | set(result["pages"]))
                doc["ocr"] = {
                    "pages": done_pages,
                    "ranges": _ranges(done_pages),
                    "engine": "tesseract",
                    "languages": OCR_LANGUAGES,
                    "placement": OCR_PLACEMENT_REVISION,
                    # Two-page photographs split in two: the OCR copy has one more page for each.
                    "split_spreads": result.get("split_spreads") or [],
                    "at": time.time(),
                    # Bibliography extraction has not read pages past the front matter as text yet.
                    "reprocess_suggested": any(p > FRONTMATTER_PAGES for p in done_pages),
                }
                doc["ocr_scan"] = scan
                if scan.get("page_count"):
                    doc["page_count"] = scan["page_count"]
                reread(doc)
                doc["updated_at"] = app_module._now()
                store.save()
                reextract = doc["ocr"]["reprocess_suggested"] and not _has_reference_work(doc)
            if reextract:
                state["state"] = "extracting"
                _reextract(app_module, doc_id)
            state.update({"state": "done", "recognised_pages": result["pages"], "finished_at": time.time()})
        except Exception as exc:  # the status route reports it; the queue keeps going
            state.update({"state": "error", "error": str(exc)})
        finally:
            _QUEUE.task_done()


def _has_reference_work(doc: Dict[str, Any]) -> bool:
    """Whether re-extracting would discard something a person did on the bibliography."""
    if doc.get("corrections") or doc.get("audit_decisions"):
        return True
    if any(s.get("source") == "manual" for s in doc.get("sections") or []):
        return True
    return any(
        r.get("edited") or r.get("deleted") or (r.get("parsed_review") or {}).get("overrides")
        for r in doc.get("references") or []
    )


def _reextract(app_module, doc_id: str) -> None:
    """Extract the bibliography again from the OCR copy, outside the store lock."""
    active = app_module.ACTIVE_ANALYSES
    if doc_id in active:
        return
    active.add(doc_id)
    store = app_module.STORE
    try:
        with store.lock:
            doc = store.docs().get(doc_id)
            path = str(doc.get("path") or "") if doc else ""
        if not path:
            return
        result = app_module.process_pdf(
            Path(path), scope="all_reference_sections", adaptive_mode="shadow",
            rescue_profile="stable", rescue_audit=True,
        )
        with store.lock:
            doc = store.docs().get(doc_id)
            if doc is None or str(doc.get("path") or "") != path or _has_reference_work(doc):
                return
            app_module._analyze_document(doc, "stable", prepared_result=result)
            store.save()
    finally:
        active.discard(doc_id)


def install_ocr(app_module, reread: Callable[[Dict[str, Any]], Any]) -> None:
    app = app_module.app
    original_analyze = app_module._analyze_document

    def analyze_document(doc, *args, **kwargs):
        result = original_analyze(doc, *args, **kwargs)
        if isinstance(doc.get("ocr"), dict):
            # The bibliography has now been extracted from the OCR text.
            doc["ocr"]["reprocess_suggested"] = False
        return result

    app_module._analyze_document = analyze_document

    @app.get("/api/ocr/status")
    def ocr_status():
        return ocr_available()

    @app.get("/api/documents/{doc_id}/ocr")
    def document_ocr(doc_id: str):
        doc = app_module.STORE.get(doc_id)
        return {"ocr_scan": doc.get("ocr_scan"), "ocr": doc.get("ocr"), "job": job_status(doc_id)}

    @app.post("/api/documents/{doc_id}/ocr")
    def run_document_ocr(doc_id: str, payload: Optional[Dict[str, Any]] = None):
        """Body: {"scope": "frontmatter" | "all" | "redo"} or {"pages": [1, 2]}."""
        _require_ocr(app_module)
        payload = payload or {}
        doc = app_module.STORE.get(doc_id)
        if payload.get("scope") == "redo":
            if not doc.get("original_path") or not Path(doc["original_path"]).exists() or not (doc.get("ocr") or {}).get("pages"):
                return {"job": job_status(doc_id), "message": "Esta tesis no tiene un OCR anterior para rehacer."}
            return {"job": _enqueue(app_module, reread, doc_id, [int(p) for p in doc["ocr"]["pages"]], redo=True)}
        pages = [int(p) for p in payload.get("pages") or []] or _pages_for_scope(doc, payload.get("scope") or "all")
        if not pages:
            return {"job": job_status(doc_id), "message": "Esta tesis no tiene páginas que necesiten OCR."}
        return {"job": _enqueue(app_module, reread, doc_id, pages)}

    @app.post("/api/projects/{project_id}/ocr")
    def run_project_ocr(project_id: str, payload: Optional[Dict[str, Any]] = None):
        """Queue OCR for every thesis in the project where it unlocks something (scope "needed")."""
        _require_ocr(app_module)
        app_module._get_project(project_id)
        scope = (payload or {}).get("scope") or "needed"
        queued = []
        with app_module.STORE.lock:
            docs = [d for d in app_module.STORE.docs().values() if d.get("project_id") == project_id]
        for doc in docs:
            pages = _pages_for_scope(doc, scope)
            if pages:
                queued.append({"document_id": doc["id"], **_enqueue(app_module, reread, doc["id"], pages)})
        return {"scope": scope, "queued": queued}

    @app.get("/api/projects/{project_id}/ocr")
    def project_ocr_status(project_id: str):
        app_module._get_project(project_id)
        with app_module.STORE.lock:
            docs = [d for d in app_module.STORE.docs().values() if d.get("project_id") == project_id]
        needing = [
            {"document_id": d["id"], "thesis_id": d.get("thesis_id"), **need}
            for d in docs for need in [ocr_need(d)] if need
        ]
        jobs = {d["id"]: status for d in docs for status in [job_status(d["id"])] if status.get("state") != "idle"}
        return {"available": ocr_available()["available"], "needing": needing, "jobs": jobs}


def _require_ocr(app_module) -> None:
    status = ocr_available()
    if not status["available"]:
        from fastapi import HTTPException
        raise HTTPException(503, status["reason"])
