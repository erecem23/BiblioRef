# -*- coding: utf-8 -*-
"""Organizing theses inside a project: folders, moves, bulk removal, saved selections.

Folders only change where a thesis is shown in BiblioRef. PDFs, references and
the folders recorded at import (``ingestion``) are never touched by a move.
"""
from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from biblioref.projects import effective_folder

MAX_FOLDER_NAME = 120
MAX_DEPTH = 12


class OrganizeError(ValueError):
    """A request that cannot be applied; the message is shown to the person."""


def clean_path(path: Any) -> List[str]:
    if path is None:
        return []
    if not isinstance(path, list):
        raise OrganizeError("La carpeta no es válida.")
    out = []
    for part in path:
        name = " ".join(str(part or "").split())
        if not name or len(name) > MAX_FOLDER_NAME or any(ord(c) < 32 for c in name):
            raise OrganizeError("El nombre de la carpeta está vacío o es demasiado largo.")
        out.append(name)
    if len(out) > MAX_DEPTH:
        raise OrganizeError("Hay demasiadas carpetas anidadas.")
    return out


def _starts_with(path: List[str], prefix: List[str]) -> bool:
    return path[:len(prefix)] == prefix


def _known_folders(project: Dict[str, Any], docs: List[Dict[str, Any]]) -> List[List[str]]:
    """Every folder path visible in the project, including ancestors."""
    seen: set = set()
    out: List[List[str]] = []
    paths = [list(p) for p in project.get("folders") or []] + [effective_folder(project, d)[0] for d in docs]
    for path in paths:
        for depth in range(1, len(path) + 1):
            key = tuple(path[:depth])
            if key not in seen:
                seen.add(key)
                out.append(list(key))
    return out


def _materialize(project: Dict[str, Any], docs: List[Dict[str, Any]]) -> None:
    """Freeze the current layout so later edits apply to what the person sees."""
    project["folders"] = _known_folders(project, docs)
    for doc in docs:
        if not isinstance(doc.get("folder"), list):
            doc["folder"] = effective_folder(project, doc)[0]


def create_folder(project: Dict[str, Any], docs: List[Dict[str, Any]], path: Any) -> List[str]:
    path = clean_path(path)
    if not path:
        raise OrganizeError("Escribí un nombre para la carpeta.")
    _materialize(project, docs)
    if any(existing == path for existing in project["folders"]):
        raise OrganizeError("Ya existe una carpeta con ese nombre en ese lugar.")
    for depth in range(1, len(path) + 1):
        if path[:depth] not in project["folders"]:
            project["folders"].append(path[:depth])
    return path


def rename_folder(project: Dict[str, Any], docs: List[Dict[str, Any]], path: Any, name: Any) -> List[str]:
    path = clean_path(path)
    new_name = clean_path([name])[0] if str(name or "").strip() else ""
    if not path or not new_name:
        raise OrganizeError("Escribí el nuevo nombre de la carpeta.")
    _materialize(project, docs)
    if path not in project["folders"]:
        raise OrganizeError("La carpeta ya no existe.")
    target = path[:-1] + [new_name]
    if target == path:
        return path
    if target in project["folders"]:
        raise OrganizeError("Ya existe una carpeta con ese nombre en ese lugar.")
    project["folders"] = [target + f[len(path):] if _starts_with(f, path) else f for f in project["folders"]]
    for doc in docs:
        if _starts_with(doc["folder"], path):
            doc["folder"] = target + doc["folder"][len(path):]
    return target


def delete_folder(project: Dict[str, Any], docs: List[Dict[str, Any]], path: Any) -> Dict[str, Any]:
    """Remove a folder; its theses and subfolders move one level up. No thesis is deleted."""
    path = clean_path(path)
    if not path:
        raise OrganizeError("No se puede eliminar la raíz del proyecto.")
    _materialize(project, docs)
    if path not in project["folders"]:
        raise OrganizeError("La carpeta ya no existe.")
    parent = path[:-1]
    moved = 0
    folders = []
    for f in project["folders"]:
        if f == path:
            continue
        new = parent + f[len(path):] if _starts_with(f, path) else f
        if new and new not in folders:
            folders.append(new)
    project["folders"] = folders
    for doc in docs:
        if _starts_with(doc["folder"], path):
            doc["folder"] = parent + doc["folder"][len(path):]
            moved += 1
    return {"parent": parent, "moved_documents": moved}


def move_documents(project: Dict[str, Any], docs: List[Dict[str, Any]], moves: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Apply [{document_id, path}]; returns the previous folders so the move can be undone."""
    by_id = {d["id"]: d for d in docs}
    planned = []
    for move in moves:
        doc = by_id.get(str(move.get("document_id")))
        if doc is None:
            raise OrganizeError("Una de las tesis ya no está en el proyecto.")
        planned.append((doc, clean_path(move.get("path"))))
    _materialize(project, docs)
    previous = []
    for doc, path in planned:
        previous.append({"document_id": doc["id"], "path": list(doc["folder"])})
        doc["folder"] = path
        for depth in range(1, len(path) + 1):
            if path[:depth] not in project["folders"]:
                project["folders"].append(path[:depth])
    return previous


def install_project_organize(app_module) -> None:
    from fastapi import HTTPException

    app = app_module.app
    store = app_module.STORE

    def scoped(project_id: str):
        project = app_module._get_project(project_id)
        docs = [d for d in store.docs().values() if d.get("project_id") == project_id]
        return project, docs

    def run(project_id: str, action):
        with store.lock:
            project, docs = scoped(project_id)
            try:
                result = action(project, docs)
            except OrganizeError as exc:
                raise HTTPException(422, str(exc))
            project["updated_at"] = time.time()
            store.save()
            return result

    @app.post("/api/projects/{project_id}/folders")
    def folders_create(project_id: str, payload: Dict[str, Any]):
        return {"path": run(project_id, lambda p, d: create_folder(p, d, payload.get("path")))}

    @app.patch("/api/projects/{project_id}/folders")
    def folders_rename(project_id: str, payload: Dict[str, Any]):
        return {"path": run(project_id, lambda p, d: rename_folder(p, d, payload.get("path"), payload.get("name")))}

    @app.post("/api/projects/{project_id}/folders/delete")
    def folders_delete(project_id: str, payload: Dict[str, Any]):
        return run(project_id, lambda p, d: delete_folder(p, d, payload.get("path")))

    @app.post("/api/projects/{project_id}/move")
    def documents_move(project_id: str, payload: Dict[str, Any]):
        """Body: {"document_ids": [...], "path": [...]} or {"moves": [{"document_id", "path"}]}."""
        moves = payload.get("moves")
        if moves is None:
            moves = [{"document_id": i, "path": payload.get("path")} for i in payload.get("document_ids") or []]
        if not moves:
            raise HTTPException(422, "Elegí al menos una tesis.")
        return {"previous": run(project_id, lambda p, d: move_documents(p, d, moves))}

    @app.post("/api/projects/{project_id}/documents/remove")
    def documents_remove(project_id: str, payload: Dict[str, Any]):
        """Remove several theses with a single save (each removal deletes the stored PDF, like «Quitar»)."""
        ids = {str(x) for x in payload.get("document_ids") or []}
        if not ids:
            raise HTTPException(422, "Elegí al menos una tesis.")
        active = getattr(app_module, "ACTIVE_ANALYSES", set())
        if ids & set(active):
            raise HTTPException(409, "Hay tesis de la selección procesándose. Esperá a que terminen.")
        with store.lock:
            _, docs = scoped(project_id)
            removed = []
            for doc in docs:
                if doc["id"] not in ids:
                    continue
                for key in ("path", "original_path", "result_file"):
                    if doc.get(key):
                        Path(doc[key]).unlink(missing_ok=True)
                store.docs().pop(doc["id"], None)
                removed.append(doc["id"])
            if removed:
                store.save()
        return {"removed": removed}

    @app.post("/api/documents/{doc_id}/sections/discard")
    def sections_discard(doc_id: str, payload: Dict[str, Any]):
        """Drop sections that are not the thesis bibliography, with their references and review alerts.

        References are marked deleted (kept in the file and in the corrections log), so nothing is lost.
        """
        with store.lock:
            doc = store.get(doc_id)
            sections = list(doc.get("sections") or [])
            drop = {int(i) for i in payload.get("indices") or [] if str(i).lstrip("-").isdigit()}
            drop = {i for i in drop if 0 <= i < len(sections)}
            if not drop:
                raise HTTPException(422, "Elegí al menos una sección.")
            if len(drop) >= len(sections):
                raise HTTPException(422, "Tiene que quedar al menos una sección de bibliografía.")
            removed = [s for i, s in enumerate(sections) if i in drop]
            kept = [s for i, s in enumerate(sections) if i not in drop]
            span = lambda s: (int(s.get("start_page") or 0), int(s.get("end_page") or s.get("start_page") or 0))
            in_ranges = lambda page, secs: any(a <= int(page or 0) <= b for a, b in map(span, secs))
            removed_zones = {s.get("zone_id") for s in removed}
            kept_zones = {s.get("zone_id") for s in kept}
            n = 0
            removed_ids = []
            for ref in doc.get("references") or []:
                if ref.get("deleted"):
                    continue
                zone = ref.get("zone_id")
                gone = zone in removed_zones and zone not in kept_zones if zone is not None else (
                    in_ranges(ref.get("start_page"), removed) and not in_ranges(ref.get("start_page"), kept))
                if gone:
                    ref["deleted"] = True
                    ref["deleted_reason"] = "section_discarded"
                    removed_ids.append(ref.get("id"))
                    n += 1
            coverage = (doc.get("analysis") or {}).get("coverage") or {}
            outside = lambda page: in_ranges(page, removed) and not in_ranges(page, kept)
            moved_alerts = {}
            for key, field in (("possible_missing", "page"), ("merged_suspects", "page"), ("page_boundaries", "page_before")):
                if isinstance(coverage.get(key), list):
                    moved_alerts[key] = [x for x in coverage[key] if outside(x.get(field))]
                    coverage[key] = [x for x in coverage[key] if not outside(x.get(field))]
            # Excluded zones are remembered with what they held, so «Incluir» restores them exactly.
            for section in removed:
                a, b = span(section)
                doc.setdefault("discarded_sections", []).append({
                    "section": section,
                    "reference_ids": [r.get("id") for r in doc.get("references") or []
                                      if r.get("id") in removed_ids and (r.get("zone_id") == section.get("zone_id")
                                                                          or a <= int(r.get("start_page") or 0) <= b)],
                    "alerts": {k: [x for x in v if a <= int(x.get("page") or x.get("page_before") or 0) <= b]
                               for k, v in moved_alerts.items()},
                })
            doc["sections"] = kept
            app_module._renumber(doc)
            doc["updated_at"] = app_module._now()
            app_module._log_correction(doc, "discard_sections", {
                "sections": [{k: s.get(k) for k in ("label", "start_page", "end_page", "zone_id")} for s in removed],
                "references_removed": n,
            })
            store.save()
            return app_module._public_doc(doc, True)

    @app.post("/api/documents/{doc_id}/sections/restore")
    def sections_restore(doc_id: str, payload: Dict[str, Any]):
        """Include again a zone that was excluded, with its references and review alerts."""
        with store.lock:
            doc = store.get(doc_id)
            discarded = doc.get("discarded_sections") or []
            try:
                index = int(payload.get("index"))
                entry = discarded[index]
            except (TypeError, ValueError, IndexError):
                raise HTTPException(422, "Esa zona ya no está excluida.")
            ids = set(entry.get("reference_ids") or [])
            restored = 0
            for ref in doc.get("references") or []:
                if ref.get("id") in ids and ref.get("deleted") and ref.get("deleted_reason") == "section_discarded":
                    ref["deleted"] = False
                    ref.pop("deleted_reason", None)
                    restored += 1
            sections = list(doc.get("sections") or []) + [entry["section"]]
            doc["sections"] = sorted(sections, key=lambda s: (int(s.get("start_page") or 0), float(s.get("start_y") or 0)))
            coverage = doc.setdefault("analysis", {}).setdefault("coverage", {})
            for key, items in (entry.get("alerts") or {}).items():
                coverage.setdefault(key, [])
                coverage[key] = list(coverage[key]) + list(items)
            discarded.pop(index)
            doc["discarded_sections"] = discarded
            app_module._renumber(doc)
            doc["updated_at"] = app_module._now()
            app_module._log_correction(doc, "restore_section", {
                "section": {k: entry["section"].get(k) for k in ("label", "start_page", "end_page", "zone_id")},
                "references_restored": restored,
            })
            store.save()
            return app_module._public_doc(doc, True)

    @app.post("/api/projects/{project_id}/reset")
    def project_reset(project_id: str, payload: Dict[str, Any]):
        """Empty a project (every thesis with its stored files, folders, selections) or, with delete_project, remove it too."""
        with store.lock:
            project, docs = scoped(project_id)
            if " ".join(str(payload.get("confirm_name") or "").split()) != " ".join(str(project.get("name") or "").split()):
                raise HTTPException(422, "Escribí el nombre exacto del proyecto para confirmar.")
            active = set(getattr(app_module, "ACTIVE_ANALYSES", set()))
            if any(d["id"] in active for d in docs):
                raise HTTPException(409, "Hay tesis procesándose. Esperá a que terminen.")
            for doc in docs:
                for key in ("path", "original_path", "result_file"):
                    if doc.get(key):
                        Path(doc[key]).unlink(missing_ok=True)
                store.docs().pop(doc["id"], None)
            deleted = bool(payload.get("delete_project"))
            if deleted:
                store.data.get("projects", {}).pop(project_id, None)
            else:
                for key in ("folders", "saved_selections"):
                    project.pop(key, None)
                project["updated_at"] = time.time()
            store.save()
        return {"removed": len(docs), "project_deleted": deleted}

    @app.get("/api/projects/{project_id}/duplicates")
    def duplicates_list(project_id: str):
        """Groups of the same PDF file loaded more than once, with the copy to keep."""
        from biblioref.duplicates import find_duplicates
        with store.lock:
            project, docs = scoped(project_id)
            missing_hash = sum(1 for d in docs if not d.get("content_sha256"))
            groups = find_duplicates(project, docs)
            if missing_hash:
                store.save()  # file hashes are cached on the theses
        return {"groups": groups, "copies_to_remove": sum(len(g["remove"]) for g in groups)}

    @app.post("/api/projects/{project_id}/duplicates/resolve")
    def duplicates_resolve(project_id: str, payload: Dict[str, Any]):
        """Remove the repeated copies of the chosen groups (by file hash). The plan is recomputed here."""
        from biblioref.duplicates import find_duplicates
        wanted = {str(x) for x in payload.get("sha256") or []}
        if not wanted:
            raise HTTPException(422, "Elegí al menos un grupo de repetidas.")
        active = set(getattr(app_module, "ACTIVE_ANALYSES", set()))
        with store.lock:
            project, docs = scoped(project_id)
            plan = [g for g in find_duplicates(project, docs) if g["sha256"] in wanted]
            if any(r["id"] in active for g in plan for r in g["remove"]):
                raise HTTPException(409, "Hay copias repetidas procesándose. Esperá a que terminen.")
            by_id = {d["id"]: d for d in docs}
            removed = []
            for group in plan:
                keep = by_id[group["keep"]["id"]]
                if group["moves_folder"]:
                    move_documents(project, docs, [{"document_id": keep["id"], "path": group["target_folder"]}])
                for item in group["remove"]:
                    doc = by_id[item["id"]]
                    for key in ("path", "original_path", "result_file"):
                        if doc.get(key) and doc.get(key) != keep.get(key):
                            Path(doc[key]).unlink(missing_ok=True)
                    store.docs().pop(doc["id"], None)
                    removed.append(item["thesis_id"] or item["id"])
                app_module._log_correction(keep, "remove_repeated_copies", {
                    "removed": [r["thesis_id"] for r in group["remove"]], "sha256": group["sha256"],
                })
                keep["updated_at"] = time.time()
            if removed:
                project["updated_at"] = time.time()
                store.save()
        return {"removed": removed, "groups": len(plan)}

    @app.post("/api/projects/{project_id}/selections")
    def selections_save(project_id: str, payload: Dict[str, Any]):
        name = " ".join(str(payload.get("name") or "").split())[:80]
        if not name:
            raise HTTPException(422, "Escribí un nombre para la selección.")
        entry = {
            "id": f"sel_{uuid.uuid4().hex[:10]}", "name": name,
            "query": str(payload.get("query") or "")[:300],
            "base": str(payload.get("base") or "")[:40],
            "created_at": time.time(),
        }

        def add(project, docs):
            project.setdefault("saved_selections", []).append(entry)
            return entry
        return run(project_id, add)

    @app.delete("/api/projects/{project_id}/selections/{selection_id}")
    def selections_delete(project_id: str, selection_id: str):
        def drop(project, docs):
            before = len(project.get("saved_selections") or [])
            project["saved_selections"] = [s for s in project.get("saved_selections") or [] if s.get("id") != selection_id]
            return {"removed": before - len(project["saved_selections"])}
        return run(project_id, drop)


__all__ = [
    "OrganizeError", "clean_path", "create_folder", "delete_folder", "install_project_organize",
    "move_documents", "rename_folder",
]
