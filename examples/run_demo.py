"""Reproducible command-line demonstration of BiblioRef.

Runs the installed ``biblioref`` command on one PDF, twice per available PDF
backend, and writes the exports of every run together with a manifest that
records the input hash, the environment, the invocation, exit codes, elapsed
times and the SHA-256 of every output file.

    python examples/run_demo.py thesis.pdf --out demo_output --expect-sha256 <hash>

The manifest reports whether repeated runs produced byte-identical exports. It
does not measure whether the extracted reference boundaries are correct.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

EXPORTS = {"--json": "result.json", "--csv": "references.csv", "--zones-csv": "zones.csv"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def available_backends() -> list[str]:
    from biblioref.ingestion.backend_context import available_pdf_backends

    return list(available_pdf_backends())


def run_once(command: list[str], pdf: Path, run_dir: Path, backend: str) -> dict:
    run_dir.mkdir(parents=True, exist_ok=True)
    args = [*command, str(pdf)]
    for flag, name in EXPORTS.items():
        args += [flag, str(run_dir / name)]
    env = {**os.environ, "BIBLIOREF_PDF_BACKEND": backend, "PYTHONIOENCODING": "utf-8"}
    started = time.perf_counter()
    completed = subprocess.run(args, env=env, capture_output=True, text=True, encoding="utf-8")
    elapsed = time.perf_counter() - started
    (run_dir / "stdout.json").write_text(completed.stdout, encoding="utf-8")
    if completed.stderr:
        (run_dir / "stderr.txt").write_text(completed.stderr, encoding="utf-8")
    outputs = {name: sha256(run_dir / name) for name in EXPORTS.values() if (run_dir / name).exists()}
    summary = {}
    if (run_dir / "result.json").exists():
        result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
        summary = {
            "n_zones": result.get("n_zones"),
            "n_records_selected": result.get("n_records_selected"),
            "detection_method": (result.get("detection_decision") or {}).get("method"),
            "zones": [
                {key: zone.get(key) for key in ("zone_id", "start_page", "end_page", "style", "n_segments", "zone_completeness")}
                for zone in result.get("zones", [])
            ],
        }
    return {
        "backend": backend,
        "invocation": [Path(args[0]).name, *args[1:]],
        "exit_code": completed.returncode,
        "elapsed_seconds": round(elapsed, 3),
        "outputs_sha256": outputs,
        "summary": summary,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--out", type=Path, default=Path("demo_output"))
    parser.add_argument("--expect-sha256", help="refuse to run if the input PDF has a different hash")
    parser.add_argument("--repeats", type=int, default=2)
    args = parser.parse_args(argv)

    pdf = args.pdf.resolve()
    input_hash = sha256(pdf)
    if args.expect_sha256 and input_hash != args.expect_sha256.lower():
        print(f"input SHA-256 {input_hash} does not match the expected {args.expect_sha256}", file=sys.stderr)
        return 2

    executable = shutil.which("biblioref")
    command = [executable] if executable else [sys.executable, "-m", "biblioref"]

    import biblioref
    from biblioref.core.config import ALGORITHM_VERSION

    runs = []
    for backend in available_backends():
        for repeat in range(1, args.repeats + 1):
            run_dir = args.out / f"{backend}_run{repeat}"
            print(f"{backend} run {repeat} ...", flush=True)
            runs.append({"run": repeat, "directory": run_dir.name, **run_once(command, pdf, run_dir, backend)})

    repeatability = {}
    for backend in {run["backend"] for run in runs}:
        hashes = [run["outputs_sha256"] for run in runs if run["backend"] == backend]
        repeatability[backend] = all(h == hashes[0] for h in hashes)

    manifest = {
        "input": {"file": pdf.name, "sha256": input_hash, "bytes": pdf.stat().st_size},
        "software": {
            "biblioref": biblioref.__version__,
            "algorithm": ALGORITHM_VERSION,
            "pypdfium2": package_version("pypdfium2"),
            "PyMuPDF": package_version("PyMuPDF"),
        },
        "environment": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "os": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "cpu_count": os.cpu_count(),
        },
        "runs": runs,
        "byte_identical_exports_across_repeats": repeatability,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: manifest[key] for key in ("input", "software", "byte_identical_exports_across_repeats")}, indent=2))
    return 0 if all(run["exit_code"] == 0 for run in runs) else 1


if __name__ == "__main__":
    raise SystemExit(main())
