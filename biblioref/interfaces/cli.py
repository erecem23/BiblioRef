"""Command-line adapter for the modular adaptive-shadow pipeline."""

import argparse
import json
from collections.abc import Sequence

from biblioref.core.config import SOFTWARE_VERSION
from biblioref.exporters import write_csv_rows, write_result_files
from biblioref.parsing import PARSER_VERSION, flatten_parsed, parse_reference
from biblioref.legacy.engine import VALID_SCOPES
from biblioref.pipeline import VALID_ADAPTIVE_MODES, process_pdf
from biblioref.rescue import PROFILE_LABELS, RESCUE_PROFILES


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=f"BiblioRef {SOFTWARE_VERSION} extraction + optional downstream bibliographic parser"
    )
    parser.add_argument("pdf", help="Input PDF")
    parser.add_argument("--json", dest="json_out", help="Output JSON")
    parser.add_argument("--csv", dest="csv_out", help="Output references CSV")
    parser.add_argument("--zones-csv", dest="zones_out", help="Output zone diagnostics CSV")
    parser.add_argument("--parsed-csv", dest="parsed_csv_out", help=f"Optional downstream parsed references CSV ({PARSER_VERSION}); does not alter extraction records")
    parser.add_argument(
        "--scope",
        choices=sorted(VALID_SCOPES),
        default="all_reference_sections",
    )
    parser.add_argument(
        "--adaptive-mode",
        choices=sorted(VALID_ADAPTIVE_MODES),
        default="shadow",
        help="off disables adaptive analysis; shadow evaluates alternatives without changing output",
    )
    parser.add_argument("--two-pass-shadow", action="store_true", help="run experimental cheap-map + selective-layout diagnostics without changing effective output")
    parser.add_argument(
        "--rescue-profile",
        choices=list(RESCUE_PROFILES),
        default="stable",
        help="stable preserves the effective v0.9.0 path; other profiles are explicit comparison candidates",
    )
    parser.add_argument(
        "--rescue-chain",
        default="",
        help="comma-separated explicit ordered rescue profiles; topology-changing rescues must be last",
    )
    parser.add_argument(
        "--no-rescue-audit",
        action="store_true",
        help="skip post-extraction anomaly audit/recommendations",
    )
    parser.add_argument("--version", action="version", version=f"BiblioRef {SOFTWARE_VERSION}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    rescue_chain = [p.strip() for p in args.rescue_chain.split(",") if p.strip()]
    result = process_pdf(args.pdf, scope=args.scope, adaptive_mode=args.adaptive_mode, two_pass_shadow=args.two_pass_shadow, rescue_profile=args.rescue_profile, rescue_audit=not args.no_rescue_audit, rescue_chain=rescue_chain)
    write_result_files(
        result,
        json_out=args.json_out,
        csv_out=args.csv_out,
        zones_out=args.zones_out,
    )
    if args.parsed_csv_out:
        parsed_rows = []
        for record in result.get("records", []):
            row = dict(record)
            parsed = parse_reference(str(record.get("reference_text") or ""))
            row.update(flatten_parsed(parsed))
            parsed_rows.append(row)
        write_csv_rows(parsed_rows, args.parsed_csv_out)
    print(json.dumps(
        {
            key: value
            for key, value in result.items()
            if key not in {"records", "zones", "duplicate_groups", "adaptive_shadow", "two_pass_shadow", "post_extraction_audit"}
        },
        ensure_ascii=False,
        indent=2,
    ))
    if "two_pass_shadow" in result:
        print(json.dumps({"two_pass_shadow_summary": {
            "proposal": result["two_pass_shadow"].get("proposal", {}),
            "effective_zone_coverage": result["two_pass_shadow"].get("effective_zone_coverage", {}),
            "eligibility_gate": result["two_pass_shadow"].get("eligibility_gate", {}),
        }}, ensure_ascii=False, indent=2))
    if "post_extraction_audit" in result:
        audit = result["post_extraction_audit"]
        print(json.dumps({"post_extraction_audit_summary": {
            "status": audit.get("status"),
            "recommendations": audit.get("recommendations", []),
            "menu": audit.get("menu", []),
        }}, ensure_ascii=False, indent=2))
    if "adaptive_shadow" in result:
        print(json.dumps({
            "adaptive_shadow_summary": {
                key: value for key, value in result["adaptive_shadow"].items()
                if key not in {"zones", "region_verifications"}
            }
        }, ensure_ascii=False, indent=2))
    return 0
