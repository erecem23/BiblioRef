# -*- coding: utf-8 -*-
"""Repeated theses: the same PDF file (same SHA-256) loaded more than once in a project.

Detection works on the file bytes, not on titles, so two different theses with
the same title are never merged and a renamed copy is still recognised. When
repeated copies are removed, the copy with the most work is kept, and it takes
the folder of a removed copy if its own folder only came from a ZIP container.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from biblioref.projects import effective_folder


class DuplicateDocument(ValueError):
    def __init__(self, existing: Dict[str, Any], filename: str):
        self.existing = existing
        code = existing.get("thesis_id") or existing.get("filename") or existing.get("id")
        super().__init__(f"{filename}: ya estaba en el proyecto como {code} (mismo archivo); no se volvió a agregar.")


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def content_hash(doc: Dict[str, Any]) -> Optional[str]:
    """SHA-256 of the thesis as imported (before OCR), cached on the document."""
    if doc.get("content_sha256"):
        return doc["content_sha256"]
    known = (doc.get("ingestion") or {}).get("sha256")
    if not known:
        source = doc.get("original_path") or doc.get("path")
        if not source or not Path(source).exists():
            return None
        try:
            known = sha256_file(source)
        except OSError:
            return None
    doc["content_sha256"] = known
    return known


def work_score(doc: Dict[str, Any]) -> int:
    """How much a person (or an explicit step) has done on this copy."""
    refs = doc.get("references") or []
    return (
        3 * len(doc.get("corrections") or [])
        + 3 * len(doc.get("audit_decisions") or {})
        + 2 * len(doc.get("metadata_inference") or {})
        + 2 * len(doc.get("metadata_confirmed") or {})
        + 2 * bool(doc.get("title_confirmed"))
        + 2 * len((doc.get("ocr") or {}).get("pages") or [])
        + sum(1 for r in refs if (r.get("parsed_review") or {}).get("overrides") or r.get("edited"))
        + (1 if doc.get("status") not in ("uploaded", "processing") else 0)
    )


def _code_number(doc: Dict[str, Any]) -> int:
    digits = "".join(ch for ch in str(doc.get("thesis_id") or "") if ch.isdigit())
    return int(digits) if digits else 10 ** 9


def _from_zip_container(doc: Dict[str, Any]) -> bool:
    rel = str((doc.get("ingestion") or {}).get("relative_path") or "").lower()
    return rel.endswith(".zip") or bool((doc.get("ingestion") or {}).get("archive_chain"))


def find_duplicates(project: Dict[str, Any], docs: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for doc in docs:
        digest = content_hash(doc)
        if digest:
            groups.setdefault(digest, []).append(doc)
    out = []
    for digest, copies in groups.items():
        if len(copies) < 2:
            continue
        ranked = sorted(copies, key=lambda d: (-work_score(d), _code_number(d)))
        keep, remove = ranked[0], ranked[1:]
        score = work_score(keep)
        if score and score > work_score(remove[0]):
            reason = "tiene más trabajo hecho (correcciones, decisiones, OCR o datos confirmados)"
        else:
            reason = "mismo archivo y sin trabajo que las distinga: se conserva el código más bajo"
        keep_folder = effective_folder(project, keep)[0]
        folder = keep_folder
        if _from_zip_container(keep):
            better = next((effective_folder(project, d)[0] for d in remove if not _from_zip_container(d)), None)
            if better and len(better) > len(keep_folder):
                folder = better
        out.append({
            "sha256": digest,
            "keep": _summary(project, keep),
            "remove": [_summary(project, d) for d in remove],
            "reason": reason,
            "target_folder": folder,
            "moves_folder": folder != keep_folder,
        })
    out.sort(key=lambda g: _code_number({"thesis_id": g["keep"]["thesis_id"]}))
    return out


def _summary(project: Dict[str, Any], doc: Dict[str, Any]) -> Dict[str, Any]:
    ing = doc.get("ingestion") or {}
    return {
        "id": doc["id"], "thesis_id": doc.get("thesis_id"), "title": doc.get("title"),
        "folder": effective_folder(project, doc)[0],
        "source": ing.get("archive_member") and f"{ing.get('relative_path')} › {ing.get('archive_member')}" or ing.get("relative_path") or doc.get("filename"),
        "n_references": doc.get("n_references") or 0, "status": doc.get("status"),
        "work": work_score(doc),
    }


def find_existing_copy(docs: Iterable[Dict[str, Any]], digest: str) -> Optional[Dict[str, Any]]:
    return next((d for d in docs if content_hash(d) == digest), None)


__all__ = ["DuplicateDocument", "content_hash", "find_duplicates", "find_existing_copy", "sha256_file", "work_score"]
