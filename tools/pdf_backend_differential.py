#!/usr/bin/env python3
"""Offline batch runner for PyMuPDF/PDFium differential validation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from biblioref.ingestion.pdf_backend_compare import compare_pdf_backends
from biblioref.ingestion.pipeline_backend_compare import compare_pipeline_backends


def _inputs(values: list[str]) -> list[Path]:
    paths: list[Path] = []
    for value in values:
        path = Path(value)
        if path.is_dir():
            paths.extend(sorted(path.glob("*.pdf")))
        elif path.suffix.lower() == ".pdf":
            paths.append(path)
    return list(dict.fromkeys(paths))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare stable PyMuPDF and experimental PDFium without changing app defaults."
    )
    parser.add_argument("pdf", nargs="+", help="PDF files or directories containing PDFs")
    parser.add_argument("--tail-pages", type=int, default=50)
    parser.add_argument("--geometry-tolerance", type=float, default=3.0)
    parser.add_argument("--skip-pipeline", action="store_true")
    parser.add_argument("--jsonl", help="Optional JSONL output path")
    args = parser.parse_args()

    pdfs = _inputs(args.pdf)
    if not pdfs:
        parser.error("No PDF inputs found")

    output_handle = Path(args.jsonl).open("w", encoding="utf-8") if args.jsonl else None
    try:
        for path in pdfs:
            from biblioref.ingestion.pdf import pdf_page_count

            pages = pdf_page_count(path)
            start_page = max(1, pages - max(1, args.tail_pages) + 1)
            report = {
                "pdf": str(path),
                "layout_tail": compare_pdf_backends(
                    path,
                    start_page=start_page,
                    end_page=pages,
                    geometry_tolerance=args.geometry_tolerance,
                ),
            }
            if not args.skip_pipeline:
                report["pipeline"] = compare_pipeline_backends(path)
            encoded = json.dumps(report, ensure_ascii=False)
            print(encoded)
            if output_handle:
                output_handle.write(encoded + "\n")
    finally:
        if output_handle:
            output_handle.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
