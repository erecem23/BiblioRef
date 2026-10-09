# -*- coding: utf-8 -*-
"""One-off repair for references split before the fix of 2026-09-18.

``split_reference`` used to copy the whole merged ``original_text`` into every
part, and the viewer locates a reference by that text: both halves claimed the
same block of the page, so the second one drew no box and every later reference
on the page was pushed onto the wrong lines. Each part now keeps its own text;
this rewrites the ones already stored.

Run it with BiblioRef closed (the app rewrites project.json on every save):

    .venv/Scripts/python.exe tools/repair_split_original_text.py
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path


try:  # consola de Windows en cp1252: que los acentos no tiren el script
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def workspace() -> Path:
    return Path(os.environ.get("BIBLIOREF_WORKSPACE", Path.home() / ".biblioref" / "projects" / "default"))


def main() -> int:
    store = workspace() / "project.json"
    if not store.exists():
        print(f"No encontré {store}")
        return 1
    data = json.loads(store.read_text(encoding="utf-8"))
    documents = data.get("documents") or {}
    documents = list(documents.values()) if isinstance(documents, dict) else documents
    repaired = []
    for doc in documents:
        for ref in doc.get("references") or []:
            if ref.get("source") != "human_split":
                continue
            if (ref.get("original_text") or "") == (ref.get("text") or ""):
                continue
            ref["original_text"] = ref.get("text") or ""
            repaired.append(f"{doc.get('thesis_id') or doc.get('id')} · REF {ref.get('order')}")
    if not repaired:
        print("No hay referencias divididas para reparar.")
        return 0
    backup = store.with_name("project.json.bak")
    shutil.copy2(store, backup)
    store.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Copia previa en {backup}")
    print(f"{len(repaired)} referencias reparadas:")
    for line in repaired:
        print(f"  {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
