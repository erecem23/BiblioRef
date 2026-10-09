#!/usr/bin/env python3
"""Profile one BiblioRef PDF extraction without changing public results."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from biblioref import pipeline
from biblioref.core.config import ALGORITHM_VERSION, SOFTWARE_VERSION
from biblioref.ingestion import clear_layout_line_cache
from biblioref.ingestion.backend_context import use_pdf_backend
from biblioref.ingestion.extraction_context import (
    ExtractionContext,
    use_extraction_context,
)


_BENCHMARK_HELP = r"""
Bash fresh-process benchmark
  for i in 1 2 3 4 5; do
    python tools/profile_single_pdf.py tests_core/fixtures/document_grammar_stress.pdf \
      --backend pdfium --reuse off --json - > "baseline-$i.json"
  done
  for i in 1 2 3 4 5; do
    python tools/profile_single_pdf.py tests_core/fixtures/document_grammar_stress.pdf \
      --backend pdfium --reuse on --json - > "optimized-$i.json"
  done

PowerShell fresh-process benchmark
  1..5 | ForEach-Object {
    python tools/profile_single_pdf.py tests_core/fixtures/document_grammar_stress.pdf `
      --backend pdfium --reuse off --json - | Out-File "baseline-$_.json" -Encoding utf8
  }
  1..5 | ForEach-Object {
    python tools/profile_single_pdf.py tests_core/fixtures/document_grammar_stress.pdf `
      --backend pdfium --reuse on --json - | Out-File "optimized-$_.json" -Encoding utf8
  }
"""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Profile one BiblioRef extraction with execution-context counters.",
        epilog=_BENCHMARK_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("pdf", help="PDF thesis to process")
    parser.add_argument(
        "--backend",
        choices=("pdfium", "pymupdf"),
        default="pdfium",
        help="PDF backend used for this run",
    )
    parser.add_argument(
        "--reuse",
        choices=("on", "off"),
        default="off",
        help="Enable or disable execution-context reuse",
    )
    parser.add_argument(
        "--adaptive-mode",
        choices=("off", "shadow"),
        default="shadow",
    )
    parser.add_argument(
        "--rescue-audit",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--json",
        dest="json_output",
        metavar="PATH_OR_DASH",
        help="Write machine JSON to a path, or '-' for JSON-only stdout",
    )
    return parser


def _human_report(
    report: dict,
    *,
    pdf: Path,
    size_bytes: int,
    mtime_ns: int,
) -> str:
    counters = report["counters"]
    timings = report["timings"]
    lines = [
        "BiblioRef single-document profile",
        "",
        f"pdf: {pdf}",
        f"pdf_sha256: {report['pdf_sha256']}",
        f"size_bytes: {size_bytes}",
        f"mtime_ns: {mtime_ns}",
        f"python: {platform.python_version()}",
        f"platform: {platform.platform()}",
        f"backend: {report['backend']}",
        f"reuse: {report['reuse_enabled']}",
        "caches_cold_at_process_start: True",
        f"total_seconds: {report['total_seconds']:.6f}",
        f"records: {report['n_records_selected']}",
        f"zones: {report['n_zones']}",
        f"coverage_status: {report['coverage_status']}",
        "",
        "counters:",
    ]
    for key in sorted(counters):
        lines.append(f"  {key}: {counters[key]}")
    lines.append("")
    lines.append("timings:")
    for key in sorted(timings):
        lines.append(f"  {key}: {timings[key]:.6f}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    pdf = Path(args.pdf).expanduser().resolve()
    stat = pdf.stat()

    clear_layout_line_cache()
    context = ExtractionContext.for_pdf(
        pdf,
        backend=args.backend,
        reuse_enabled=args.reuse == "on",
    )
    context.size_bytes = int(stat.st_size)
    context.mtime_ns = int(stat.st_mtime_ns)

    with use_pdf_backend(args.backend), use_extraction_context(context):
        started = perf_counter()
        result = pipeline.process_pdf(
            pdf,
            adaptive_mode=args.adaptive_mode,
            rescue_audit=args.rescue_audit,
        )
        total_seconds = perf_counter() - started

    coverage = result.get("coverage_report") or {}
    report = {
        "pdf_sha256": _sha256(pdf),
        "backend": args.backend,
        "reuse_enabled": bool(context.reuse_enabled),
        "total_seconds": total_seconds,
        "algorithm_version": result.get("algorithm_version", ALGORITHM_VERSION),
        "software_version": result.get("software_version", SOFTWARE_VERSION),
        "n_records_selected": int(
            result.get("n_records_selected", len(result.get("records", []) or []))
        ),
        "n_zones": len(result.get("zones", []) or []),
        "coverage_status": coverage.get("status"),
        "counters": dict(context.counters),
        "timings": dict(context.timings),
    }

    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    human = _human_report(
        report,
        pdf=pdf,
        size_bytes=int(stat.st_size),
        mtime_ns=int(stat.st_mtime_ns),
    )
    if args.json_output == "-":
        print(encoded)
        print(human, file=sys.stderr)
    else:
        print(human)
        if args.json_output:
            Path(args.json_output).write_text(encoded + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
