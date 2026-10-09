# -*- coding: utf-8 -*-
"""Inference of missing thesis metadata, applied only on request and auditable.

Inferring is not extracting: the value is not written in the PDF, it is deduced
from other data of the same thesis or of other theses in the project. Each
inferred value is stored in ``doc["metadata_inference"][field]`` with its rule
and evidence, only fills empty cells, and can be confirmed or undone.
"""
from __future__ import annotations

import re
import time
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

RULES = {
    "program_from_level_faculty": {
        "field": "program",
        "title": "Programa desde nivel y facultad",
        "description": "Si la tesis es de doctorado, maestría o especialización y la facultad es de una sola "
                       "disciplina («Facultad de Psicología»), el programa es «Doctorado en Psicología».",
    },
    "faculty_from_peers": {
        "field": "faculty",
        "title": "Facultad desde otras tesis del proyecto",
        "description": "Si al menos 3 tesis con la misma universidad y el mismo programa tienen la facultad "
                       "leída del PDF, y todas coinciden, se usa esa facultad.",
    },
    "university_from_repository": {
        "field": "university",
        "title": "Universidad desde el repositorio citado",
        "description": "Si el PDF cita en sus primeras páginas el repositorio institucional de una sola universidad.",
    },
}
# Evaluated in this order: a university found by its repository can then group a
# thesis with its peers, and a faculty can then name the program.
RULE_ORDER = ("university_from_repository", "faculty_from_peers", "program_from_level_faculty")
NOT_INFERRED = {
    "title": "No se infiere: universidad desde el programa",
    "description": "«Doctorado en Psicología» existe en varias universidades del proyecto: sería adivinar.",
}

REPOSITORY_UNIVERSITIES = {
    "rdu.unc.edu.ar": "Universidad Nacional de Córdoba",
    "unlp.edu.ar": "Universidad Nacional de La Plata",
    "mdp.edu.ar": "Universidad Nacional de Mar del Plata",
    "repositorio.uba.ar": "Universidad de Buenos Aires",
}
REPOSITORY_PAGES = 3
MIN_PEERS = 3
_LEVEL_HEADS = {"doctorado": "Doctorado", "maestria": "Maestría", "especializacion": "Especialización"}
_SINGLE_DISCIPLINE_FACULTY = re.compile(r"Facultad de ([A-ZÁÉÍÓÚÑ][a-záéíóúñü]+)")


def _text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def inference_of(doc: Dict[str, Any], field: str) -> Optional[Dict[str, Any]]:
    """The inference behind a field, only while the field still holds the inferred value."""
    entry = (doc.get("metadata_inference") or {}).get(field)
    if entry and _text((doc.get("metadata") or {}).get(field)) == _text(entry.get("value")):
        return entry
    return None


def _read_value(doc: Dict[str, Any], field: str) -> str:
    """A value that was read or edited, never one inferred."""
    if inference_of(doc, field):
        return ""
    return _text((doc.get("metadata") or {}).get(field))


def _repository_text(path: str) -> str:
    import pymupdf
    with pymupdf.open(path) as pdf:
        return " ".join(pdf[i].get_text() for i in range(min(REPOSITORY_PAGES, pdf.page_count))).lower()


def propose_inferences(
    docs: List[Dict[str, Any]],
    rules: Optional[Iterable[str]] = None,
    read_text: Callable[[str], str] = _repository_text,
) -> List[Dict[str, Any]]:
    """Inferences for empty cells, without touching the documents."""
    wanted = [r for r in RULE_ORDER if rules is None or r in set(rules)]
    # Working copy of the values each rule can see, including earlier rules' results.
    values = {d["id"]: {k: _text(v) for k, v in (d.get("metadata") or {}).items()} for d in docs}
    out: List[Dict[str, Any]] = []

    def add(doc, rule, value, evidence):
        field = RULES[rule]["field"]
        values[doc["id"]][field] = value
        out.append({"document_id": doc["id"], "thesis_id": doc.get("thesis_id"), "field": field,
                    "value": value, "rule": rule, "evidence": evidence})

    for rule in wanted:
        field = RULES[rule]["field"]
        for doc in docs:
            if values[doc["id"]].get(field):
                continue
            meta = values[doc["id"]]
            if rule == "university_from_repository":
                path = str(doc.get("path") or "")
                if not path or not Path(path).exists():
                    continue
                try:
                    text = read_text(path)
                except Exception:
                    continue
                hits = {u: domain for domain, u in REPOSITORY_UNIVERSITIES.items() if domain in text}
                if len(hits) == 1:
                    university, domain = next(iter(hits.items()))
                    add(doc, rule, university, f"El PDF cita «{domain}» en sus primeras {REPOSITORY_PAGES} páginas.")
            elif rule == "faculty_from_peers":
                university, program = meta.get("university"), meta.get("program")
                if not university or not program:
                    continue
                peers = Counter(
                    _read_value(o, "faculty") for o in docs
                    if o["id"] != doc["id"] and _read_value(o, "faculty")
                    and values[o["id"]].get("university") == university and values[o["id"]].get("program") == program
                )
                total = sum(peers.values())
                if total >= MIN_PEERS and len(peers) == 1:
                    faculty = next(iter(peers))
                    add(doc, rule, faculty,
                        f"{total} de {total} tesis de {university} · {program} tienen «{faculty}» leída del PDF.")
            elif rule == "program_from_level_faculty":
                level, faculty = meta.get("degree_level", "").casefold(), meta.get("faculty", "")
                match = _SINGLE_DISCIPLINE_FACULTY.fullmatch(faculty)
                if level in _LEVEL_HEADS and match:
                    program = f"{_LEVEL_HEADS[level]} en {match.group(1)}"
                    inferred = " (facultad inferida)" if any(
                        x["document_id"] == doc["id"] and x["field"] == "faculty" for x in out
                    ) or inference_of(doc, "faculty") else ""
                    add(doc, rule, program, f"Nivel «{level}» · {faculty}{inferred}.")
    return out


def apply_inferences(docs_by_id: Dict[str, Dict[str, Any]], proposals: List[Dict[str, Any]], now: float | None = None) -> int:
    applied = 0
    stamp = now or time.time()
    for item in proposals:
        doc = docs_by_id.get(item["document_id"])
        if doc is None:
            continue
        meta = doc.setdefault("metadata", {})
        if _text(meta.get(item["field"])):
            continue  # never overwrite a read or edited value
        meta[item["field"]] = item["value"]
        doc.setdefault("metadata_inference", {})[item["field"]] = {
            "value": item["value"], "rule": item["rule"], "evidence": item["evidence"], "at": stamp,
        }
        applied += 1
    return applied


def undo_inference(doc: Dict[str, Any], field: str) -> bool:
    entry = (doc.get("metadata_inference") or {}).pop(field, None)
    if entry is None:
        return False
    meta = doc.get("metadata") or {}
    if _text(meta.get(field)) == _text(entry.get("value")):
        meta.pop(field, None)
    return True


def confirm_inference(doc: Dict[str, Any], field: str) -> Optional[Dict[str, Any]]:
    """Keep the value as a person's decision: it stops being marked as inferred."""
    entry = inference_of(doc, field)
    if entry is None:
        return None
    doc["metadata_inference"].pop(field, None)
    doc.setdefault("metadata_confirmed", {})[field] = {"value": entry["value"], "from_rule": entry.get("rule"), "at": time.time()}
    return entry


def public_inference(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        field: {**entry, "rule_title": RULES.get(entry.get("rule"), {}).get("title", entry.get("rule"))}
        for field in list((doc.get("metadata_inference") or {}))
        for entry in [inference_of(doc, field)] if entry
    }


def field_origin(doc: Dict[str, Any], field: str) -> str:
    """For exports: where a metadata value comes from."""
    value = _text((doc.get("metadata") or {}).get(field))
    if not value:
        return ""
    if inference_of(doc, field):
        return "inferido"
    suggestion = ((doc.get("metadata_detection") or {}).get("suggestions") or {}).get(field)
    return "PDF" if _text(suggestion) == value else "manual"


EXPORT_FIELDS = ("author", "year", "degree_level", "program", "faculty", "university", "director", "codirector")


def install_inference(app_module) -> None:
    from fastapi import HTTPException

    app = app_module.app

    def project_docs(project_id: str) -> List[Dict[str, Any]]:
        app_module._get_project(project_id)
        return [d for d in app_module.STORE.docs().values() if d.get("project_id") == project_id]

    @app.get("/api/projects/{project_id}/inference/preview")
    def inference_preview(project_id: str):
        with app_module.STORE.lock:
            docs = project_docs(project_id)
        proposals = propose_inferences(docs)
        rules = []
        for rule in RULE_ORDER:
            items = [p for p in proposals if p["rule"] == rule]
            rules.append({"id": rule, **RULES[rule], "count": len(items), "example": items[0] if items else None})
        return {"rules": rules, "not_inferred": NOT_INFERRED, "total": len(proposals)}

    @app.post("/api/projects/{project_id}/inference")
    def inference_apply(project_id: str, payload: Optional[Dict[str, Any]] = None):
        rules = (payload or {}).get("rules")
        if rules is not None and not set(rules) <= set(RULES):
            raise HTTPException(422, "Regla de inferencia desconocida.")
        with app_module.STORE.lock:
            docs = project_docs(project_id)
            proposals = propose_inferences(docs, rules)
            applied = apply_inferences({d["id"]: d for d in docs}, proposals, app_module._now())
            for doc_id in {p["document_id"] for p in proposals}:
                doc = app_module.STORE.docs()[doc_id]
                doc["updated_at"] = app_module._now()
                fields = [p for p in proposals if p["document_id"] == doc_id]
                app_module._log_correction(doc, "infer_metadata", {"inferences": fields})
            if applied:
                app_module.STORE.save()
        return {"applied": applied}

    def edit(doc_id: str, field: str, action: str):
        with app_module.STORE.lock:
            doc = app_module.STORE.get(doc_id)
            entry = inference_of(doc, field)
            if entry is None:
                raise HTTPException(404, "Ese dato no está marcado como inferido.")
            if action == "undo":
                undo_inference(doc, field)
            else:
                confirm_inference(doc, field)
            doc["updated_at"] = app_module._now()
            app_module._log_correction(doc, f"{action}_inferred_metadata", {"field": field, **entry})
            app_module.STORE.save()
            return app_module._public_doc(doc, False)

    @app.post("/api/documents/{doc_id}/inference/{field}/undo")
    def inference_undo(doc_id: str, field: str):
        return edit(doc_id, field, "undo")

    @app.post("/api/documents/{doc_id}/inference/{field}/confirm")
    def inference_confirm(doc_id: str, field: str):
        return edit(doc_id, field, "confirm")

    @app.post("/api/projects/{project_id}/inference/undo-all")
    def inference_undo_all(project_id: str, payload: Optional[Dict[str, Any]] = None):
        only = (payload or {}).get("field")
        undone = 0
        with app_module.STORE.lock:
            for doc in project_docs(project_id):
                fields = [f for f in list(doc.get("metadata_inference") or {}) if not only or f == only]
                done = [f for f in fields if inference_of(doc, f) and undo_inference(doc, f)]
                if done:
                    undone += len(done)
                    doc["updated_at"] = app_module._now()
                    app_module._log_correction(doc, "undo_inferred_metadata", {"fields": done})
            if undone:
                app_module.STORE.save()
        return {"undone": undone}


__all__ = [
    "EXPORT_FIELDS", "NOT_INFERRED", "RULES", "RULE_ORDER", "apply_inferences", "confirm_inference",
    "field_origin", "inference_of", "install_inference", "propose_inferences", "public_inference", "undo_inference",
]
