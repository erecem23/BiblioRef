#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create a reproducible BiblioRef field-test bundle from an exported CSV.

This helper is intentionally outside the extraction/parser/profiler core. It reads
an ordinary BiblioRef CSV export and writes diagnostics without changing the CSV
or rerunning extraction.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from biblioref.core.config import ALGORITHM_VERSION, SOFTWARE_VERSION, STABLE_ENGINE_VERSION
from biblioref.parsing import PARSER_VERSION
from biblioref.styleprofiler import STYLE_PROFILER_VERSION, extract_reference_features, profile_document


PARSED_COLUMNS = {
    "parser_version": "parsed_parser_version",
    "parser_status": "parsed_parser_status",
    "parse_style": "parsed_parse_style",
    "author": "parsed_author",
    "authors": "parsed_authors",
    "year": "parsed_year",
    "publication_type": "parsed_publication_type",
    "title": "parsed_title",
    "journal": "parsed_journal",
    "publisher": "parsed_publisher",
    "publisher_observed": "parsed_publisher_observed",
    "source_publisher": "parsed_source_publisher",
    "doi": "parsed_doi",
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _safe_stem(value: str) -> str:
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return s.strip("._") or "biblioref_field_test"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            raise ValueError("El CSV no tiene encabezados.")
        required = {"text", "reference_id", "order"}
        missing = sorted(required - set(reader.fieldnames))
        if missing:
            raise ValueError("No parece un CSV de BiblioRef; faltan columnas: " + ", ".join(missing))
        return [dict(row) for row in reader]


def _parsed_from_row(row: dict[str, str]) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for key, col in PARSED_COLUMNS.items():
        value = row.get(col, "")
        if key == "authors" and value:
            try:
                value = json.loads(value)
            except Exception:
                pass
        parsed[key] = value or None
    return parsed


def _profile_rows(rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for idx, row in enumerate(rows, 1):
        try:
            order: Any = int(row.get("order") or idx)
        except Exception:
            order = idx
        refs.append({
            "id": row.get("reference_id") or f"r{idx:04d}",
            "order": order,
            "zone_id": row.get("zone_id") or "unassigned",
            "text": row.get("text") or "",
            "parsed": _parsed_from_row(row),
        })
    context = {
        "country": next((r.get("country") for r in rows if r.get("country")), None),
        "institution": next((r.get("university") for r in rows if r.get("university")), None),
        "discipline": next((r.get("area") for r in rows if r.get("area")), None),
        "publication_year": next((r.get("year") for r in rows if r.get("year")), None),
        "source": "field_test_csv_export",
    }
    return refs, profile_document(refs, context=context, include_references=True)


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def build_bundle(csv_path: Path, out_dir: Path) -> Path:
    rows = _read_csv(csv_path)
    refs, style_profile = _profile_rows(rows)
    out_dir.mkdir(parents=True, exist_ok=True)

    doc_id = next((r.get("document_id") for r in rows if r.get("document_id")), "document")
    thesis_id = next((r.get("thesis_id") for r in rows if r.get("thesis_id")), "")
    base = _safe_stem(f"{thesis_id}_{doc_id}" if thesis_id else doc_id)

    style_path = out_dir / f"{base}_style_profile.json"
    style_path.write_text(json.dumps(style_profile, ensure_ascii=False, indent=2), encoding="utf-8")

    local_profiles: dict[str, dict[str, Any]] = {}
    for zone in style_profile.get("zones", []):
        for item in zone.get("references", []) or []:
            local_profiles[str(item.get("reference_id"))] = item

    diag_rows: list[dict[str, Any]] = []
    for original, ref in zip(rows, refs):
        parsed = ref["parsed"]
        feat = extract_reference_features(ref["text"], parsed)
        local = local_profiles.get(str(ref["id"]), {})
        diag = {
            "thesis_id": original.get("thesis_id", ""),
            "document_id": original.get("document_id", ""),
            "reference_id": ref["id"],
            "order": ref["order"],
            "zone_id": ref["zone_id"],
            "start_page": original.get("start_page", ""),
            "end_page": original.get("end_page", ""),
            "text": ref["text"],
            "parse_style": parsed.get("parse_style") or "",
            "parser_status": parsed.get("parser_status") or "",
            "parsed_author": parsed.get("author") or "",
            "parsed_year": parsed.get("year") or "",
            "parsed_publication_type": parsed.get("publication_type") or "",
            "parsed_title": parsed.get("title") or "",
            "parsed_journal": parsed.get("journal") or "",
            "parsed_publisher": parsed.get("publisher") or "",
            "parsed_doi": parsed.get("doi") or "",
            "profile_family": local.get("family", ""),
            "profile_likely_style": local.get("likely_style", ""),
            "profile_variant": local.get("variant", ""),
            "profile_evidence_score": local.get("evidence_score", ""),
        }
        diag.update({f"feat_{k}": v for k, v in feat.items() if k != "publication_type"})
        diag_rows.append(diag)

    diag_fields = list(diag_rows[0].keys()) if diag_rows else ["reference_id", "order", "text"]
    diag_path = out_dir / f"{base}_parser_profiler_diagnostics.csv"
    _write_csv(diag_path, diag_fields, diag_rows)

    review_rows = []
    for d in diag_rows:
        review_rows.append({
            "reference_id": d.get("reference_id"),
            "order": d.get("order"),
            "start_page": d.get("start_page"),
            "text": d.get("text"),
            "parsed_author": d.get("parsed_author"),
            "parsed_year": d.get("parsed_year"),
            "parsed_publication_type": d.get("parsed_publication_type"),
            "parsed_title": d.get("parsed_title"),
            "parsed_journal": d.get("parsed_journal"),
            "parsed_publisher": d.get("parsed_publisher"),
            "review_status": "",
            "issue_category": "",
            "expected_value": "",
            "note": "",
        })
    review_fields = list(review_rows[0].keys()) if review_rows else ["reference_id", "order", "text", "review_status", "issue_category", "note"]
    review_path = out_dir / f"{base}_optional_review_template.csv"
    _write_csv(review_path, review_fields, review_rows)

    route_counts = Counter((r["parsed"].get("parse_style") or "unknown") for r in refs)
    type_counts = Counter((r["parsed"].get("publication_type") or "sin_clasificar") for r in refs)
    fields = ["author", "year", "title", "journal", "publisher", "doi"]
    coverage = {
        field: round(sum(bool(r["parsed"].get(field)) for r in refs) / len(refs), 4) if refs else 0.0
        for field in fields
    }
    observed_parser_versions = sorted({str(r["parsed"].get("parser_version") or "") for r in refs})
    parser_version_mismatch = any(v and v != PARSER_VERSION for v in observed_parser_versions)
    manifest = {
        "bundle_schema": "biblioref-field-test-1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input": {
            "filename": csv_path.name,
            "sha256": _sha256(csv_path),
            "n_references": len(refs),
            "n_zones": len({str(r.get("zone_id") or "unassigned") for r in refs}),
        },
        "versions": {
            "software_version": SOFTWARE_VERSION,
            "algorithm_version": ALGORITHM_VERSION,
            "stable_engine_version": STABLE_ENGINE_VERSION,
            "parser_version_expected": PARSER_VERSION,
            "styleprofiler_version": STYLE_PROFILER_VERSION,
            "core_mutated_by_helper": False,
        },
        "observed_parser_versions": observed_parser_versions,
        "parser_version_mismatch": parser_version_mismatch,
        "parse_route_distribution": dict(route_counts),
        "publication_type_distribution": dict(type_counts),
        "parsed_field_coverage": coverage,
        "style_zone_summary": [
            {
                "zone_id": z.get("zone_id"),
                "n_references": (z.get("evidence") or {}).get("n_references"),
                "family": z.get("family"),
                "likely_style": z.get("likely_style"),
                "variant": z.get("variant"),
                "consistency": z.get("consistency"),
                "mixed_style": z.get("mixed_style"),
            }
            for z in style_profile.get("zones", [])
        ],
        "files": {
            "style_profile": style_path.name,
            "diagnostics": diag_path.name,
            "optional_review_template": review_path.name,
        },
        "warnings": ([f"El CSV fue generado con {', '.join(v for v in observed_parser_versions if v)}, pero este paquete espera {PARSER_VERSION}. El helper conserva el parseo observado y NO lo reejecuta."] if parser_version_mismatch else []),
        "interpretation_warning": "StyleProfiler v0.1 is shadow-only. likely_style is morphological similarity, not normative compliance. evidence_score is not a calibrated probability.",
    }
    manifest_path = out_dir / f"{base}_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    zip_path = out_dir / f"{base}_FIELD_TEST_BUNDLE.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(csv_path, arcname=f"original/{csv_path.name}")
        for p in (manifest_path, style_path, diag_path, review_path):
            zf.write(p, arcname=p.name)
    return zip_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Genera un bundle diagnóstico reproducible desde un CSV exportado por BiblioRef.")
    parser.add_argument("csv", type=Path, help="CSV exportado por BiblioRef")
    parser.add_argument("--out", type=Path, default=Path("field_test_output"), help="Carpeta de salida")
    args = parser.parse_args(argv)
    try:
        bundle = build_bundle(args.csv, args.out)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(bundle.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
