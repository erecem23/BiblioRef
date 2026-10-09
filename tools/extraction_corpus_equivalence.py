# -*- coding: utf-8 -*-
"""Arnés de equivalencia del extractor sobre un corpus completo.

`EXTRACTION_EQUIVALENCE_V097.json` prueba la equivalencia con dos tesis. Esto la
prueba con las 121 del corpus de tesis doctorales de Psicología: corre
``biblioref.pipeline.process_pdf`` sobre cada PDF del workspace y guarda, por
tesis, el conteo de registros y el sha256 del texto de todos ellos.

La línea de base queda en ``EXTRACTION_CORPUS_EQUIVALENCE_V0_1.json`` (compacto,
versionable). Un cambio en el núcleo se declara mostrando qué tesis cambiaron y
cuáles siguen idénticas.

    # línea de base
    python tools/extraction_corpus_equivalence.py --out EXTRACTION_CORPUS_EQUIVALENCE_V0_1.json

    # después de tocar el núcleo
    python tools/extraction_corpus_equivalence.py --out /tmp/nuevo.json \
        --baseline EXTRACTION_CORPUS_EQUIVALENCE_V0_1.json

    # iteración rápida: sólo las tesis que el cambio debería tocar, más controles
    python tools/extraction_corpus_equivalence.py --ids T0034,T0070,T0117 \
        --baseline EXTRACTION_CORPUS_EQUIVALENCE_V0_1.json --out /tmp/rapido.json

``--dump`` escribe además el texto completo de cada registro en un archivo aparte,
para poder mirar un diff concreto; ese archivo no se versiona.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_WORKSPACE = Path.home() / ".biblioref" / "projects" / "default"


def _load_documents(workspace: Path) -> Dict[str, dict]:
    project = workspace / "project.json"
    if not project.exists():
        raise SystemExit(f"no encuentro {project}")
    data = json.loads(project.read_text(encoding="utf-8"))
    return data.get("documents") or {}


def _corpus(documents: Dict[str, dict]) -> List[tuple]:
    """(thesis_id, document_id, pdf_path) ordenado por thesis_id."""
    rows = []
    for document_id, record in documents.items():
        thesis_id = record.get("thesis_id")
        path = record.get("path")
        if not thesis_id or not path:
            continue
        rows.append((thesis_id, document_id, path))
    return sorted(rows)


def _digest(texts: List[str]) -> str:
    joined = "\n".join(texts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def run(workspace: Path, ids: Optional[List[str]]) -> dict:
    from biblioref.core.config import ALGORITHM_VERSION, SOFTWARE_VERSION
    from biblioref.pipeline import process_pdf

    wanted = set(ids) if ids else None
    rows = _corpus(_load_documents(workspace))
    if wanted:
        rows = [row for row in rows if row[0] in wanted]
    entries = []
    started = time.time()
    for index, (thesis_id, document_id, path) in enumerate(rows, 1):
        entry = {"thesis_id": thesis_id, "document_id": document_id}
        if not os.path.exists(path):
            entry["error"] = "pdf_ausente"
        else:
            try:
                report = process_pdf(path)
                texts = [record["reference_text"] for record in report["records"]]
                entry.update({
                    "n_records": len(texts),
                    "n_zones": report["n_zones"],
                    "records_sha256": _digest(texts),
                    "zones": [
                        {
                            "heading": zone["heading"][:60],
                            "start_page": zone["start_page"],
                            "end_page": zone["end_page"],
                            "style": zone["style"],
                            "n_segments": zone["n_segments"],
                        }
                        for zone in report["zones"]
                    ],
                    "_texts": texts,
                })
            except Exception as exc:  # noqa: BLE001 - se reporta, no se traga
                entry["error"] = f"{type(exc).__name__}: {exc}"
        entries.append(entry)
        print(
            f"[{index}/{len(rows)}] {thesis_id} "
            f"{entry.get('n_records', entry.get('error'))}",
            flush=True,
        )
    return {
        "software_version": SOFTWARE_VERSION,
        "algorithm_version": ALGORITHM_VERSION,
        "corpus": "tesis doctorales de Psicologia",
        "n_documents": len(entries),
        "elapsed_seconds": round(time.time() - started, 1),
        "documents": entries,
    }


def compare(baseline: dict, current: dict) -> dict:
    previous = {d["thesis_id"]: d for d in baseline["documents"]}
    identical, changed, missing = [], [], []
    for entry in current["documents"]:
        thesis_id = entry["thesis_id"]
        before = previous.get(thesis_id)
        if before is None:
            missing.append(thesis_id)
            continue
        if before.get("records_sha256") == entry.get("records_sha256"):
            identical.append(thesis_id)
        else:
            changed.append({
                "thesis_id": thesis_id,
                "n_records_before": before.get("n_records"),
                "n_records_after": entry.get("n_records"),
                "delta": (entry.get("n_records") or 0) - (before.get("n_records") or 0),
            })
    changed.sort(key=lambda x: -x["delta"])
    total_before = sum(d.get("n_records") or 0 for d in baseline["documents"])
    total_after = sum(d.get("n_records") or 0 for d in current["documents"])
    return {
        "n_compared": len(identical) + len(changed),
        "n_identical": len(identical),
        "n_changed": len(changed),
        "sin_linea_de_base": missing,
        "total_records_before": total_before,
        "total_records_after": total_after,
        "delta_records": total_after - total_before,
        "changed": changed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--ids", default="", help="lista separada por comas")
    parser.add_argument("--dump", type=Path, help="texto completo de cada registro")
    args = parser.parse_args()

    ids = [x.strip() for x in args.ids.split(",") if x.strip()] or None
    result = run(args.workspace, ids)

    texts = {d["thesis_id"]: d.pop("_texts") for d in result["documents"] if "_texts" in d}
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nescrito: {args.out}")
    if args.dump:
        args.dump.write_text(json.dumps(texts, ensure_ascii=False), encoding="utf-8")
        print(f"textos: {args.dump}")

    if args.baseline:
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
        diff = compare(baseline, result)
        print(
            f"\nidenticas {diff['n_identical']}/{diff['n_compared']} | "
            f"cambiadas {diff['n_changed']} | "
            f"registros {diff['total_records_before']} -> "
            f"{diff['total_records_after']} ({diff['delta_records']:+d})"
        )
        for row in diff["changed"]:
            print(
                f"  {row['thesis_id']}: {row['n_records_before']} -> "
                f"{row['n_records_after']} ({row['delta']:+d})"
            )
        if diff["sin_linea_de_base"]:
            print("sin linea de base:", ", ".join(diff["sin_linea_de_base"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
