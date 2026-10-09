"""Project ownership and original folder layout, independent of extraction."""
from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

PROJECTS_VERSION = "projects-v0.1"
LEGACY_PROJECT_ID = "project_legacy"


def relative_path(value: str) -> str:
    """Validate a display path. It is never used as a filesystem destination."""
    raw = str(value or "").replace("\\", "/")
    path = PurePosixPath(raw)
    if (not raw or raw.startswith("/") or ".." in path.parts
            or any(":" in p or any(ord(c) < 32 for c in p) for p in path.parts)):
        raise ValueError("La ruta debe ser relativa y no puede contener '..'.")
    if not path.parts or len(raw) > 4096 or len(path.parts) > 64:
        raise ValueError("La ruta de carpetas no es válida o es demasiado extensa.")
    return "/".join(path.parts)


def document_folders(doc: dict[str, Any]) -> list[str]:
    ingestion = doc.get("ingestion") or {}
    folders: list[str] = []
    try:
        source_path = ingestion.get("relative_path") or ""
        if source_path:
            folders.extend(relative_path(source_path).split("/")[:-1])
        chain = ingestion.get("archive_chain") or []
        # The outer archive is a container, not a replacement for its folders.
        for nested in chain[1:]:
            folders.extend(relative_path(nested).split("/"))
        member = ingestion.get("archive_member") or ""
        if member:
            folders.extend(relative_path(member).split("/")[:-1])
    except ValueError:
        # Historical provenance is display-only; never interpret unsafe paths.
        return []
    return folders


def effective_folder(project: dict[str, Any], doc: dict[str, Any]) -> tuple[list[str], bool]:
    """Folder where the thesis is shown, and whether it came from a suggested university.

    A folder chosen in BiblioRef (``doc["folder"]``) wins over the folders of the
    import, which stay recorded in ``ingestion`` as provenance.
    """
    if isinstance(doc.get("folder"), list):
        return [str(x) for x in doc["folder"]], False
    folders = document_folders(doc)
    if not folders and project.get("group_loose_by_university"):
        university = (doc.get("metadata") or {}).get("university")
        detected = (doc.get("metadata_detection") or {}).get("suggestions") or {}
        return [str(university or "Universidad sin identificar")], bool(university and university == detected.get("university"))
    return folders, False


def project_tree(project: dict[str, Any], docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Folders chosen in BiblioRef, then import folders; optional university grouping covers loose PDFs."""
    root: dict[str, Any] = {"children": {}}
    # Folders created in BiblioRef exist even while empty.
    for path in project.get("folders") or []:
        node = root
        for name in path:
            node = node["children"].setdefault(("folder", name), {"kind": "folder", "name": name, "children": {}})
    for doc in docs:
        folders, inferred = effective_folder(project, doc)
        node = root
        for name in folders:
            # Keep the full label as one node even when a university has a slash.
            node = node["children"].setdefault(("folder", name), {
                "kind": "folder", "name": name, "children": {},
            })
        ing = doc.get("ingestion") or {}
        name = str(ing.get("archive_member") or ing.get("relative_path") or doc.get("filename") or "Tesis.pdf").replace("\\", "/").rsplit("/", 1)[-1]
        node["children"][("document", doc["id"])] = {
            "kind": "document", "id": doc["id"], "name": name,
            "title": doc.get("title") or name, "status": doc.get("status"),
            "university_suggested": inferred,
        }

    def flatten(node):
        result = []
        for child in sorted(node["children"].values(), key=lambda x: (x["kind"] != "folder", x["name"].casefold())):
            if child["kind"] == "folder":
                child["children"] = flatten(child)
                child["count"] = sum(x.get("count", 0) if x["kind"] == "folder" else 1 for x in child["children"])
            result.append(child)
        return result

    return flatten(root)
