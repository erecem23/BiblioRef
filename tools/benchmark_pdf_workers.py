"""Measure PDF import preparation, including cold process startup.

python benchmark_pdf_workers.py --synthetic 24 --workers 4
python benchmark_pdf_workers.py thesis1.pdf thesis2.pdf --workers 4

This measures preflight, title and cover reading, not upload speed or the full
bibliography pipeline. Synthetic PDFs are explicitly labeled and temporary.
"""
from concurrent.futures import ProcessPoolExecutor
import argparse
import json
import multiprocessing
from pathlib import Path
import tempfile
import time

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from biblioref.pdf_workers import prepare_pdf, worker_count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdfs", nargs="*")
    parser.add_argument("--synthetic", type=int, default=0)
    parser.add_argument("--workers", type=int, default=worker_count())
    args = parser.parse_args()
    if not args.pdfs and args.synthetic < 1:
        parser.error("Provide PDFs or --synthetic N")
    with tempfile.TemporaryDirectory(prefix="biblioref_benchmark_") as directory:
        paths = [Path(p) for p in args.pdfs]
        if args.synthetic:
            import fitz
            for i in range(args.synthetic):
                path = Path(directory) / f"tesis_{i + 1:03}.pdf"
                with fitz.open() as doc:
                    cover = doc.new_page()
                    for y, text, size in [(100, "UNIVERSIDAD NACIONAL DE LA PLATA", 14),
                                          (260, "Procesos educativos y experiencias colectivas", 20),
                                          (305, f"Estudio de caso {i + 1}", 18),
                                          (440, "Autor: Juan Perez", 14), (650, "2024", 14)]:
                        cover.insert_text((60, y), text, fontsize=size)
                    for page in range(39):
                        doc.new_page().insert_textbox((60, 60, 530, 780),
                            (f"Capitulo {page + 1}. Analisis de las practicas educativas. " * 60), fontsize=11)
                    doc.save(path)
                paths.append(path)
        start = time.perf_counter()
        serial = [prepare_pdf(str(path), path.name) for path in paths]
        serial_seconds = time.perf_counter() - start
        start = time.perf_counter()
        with ProcessPoolExecutor(args.workers, mp_context=multiprocessing.get_context("spawn")) as pool:
            parallel = list(pool.map(prepare_pdf, map(str, paths), [p.name for p in paths]))
        parallel_seconds = time.perf_counter() - start
        equivalent = serial == parallel
        print(json.dumps({"pdfs": len(paths), "synthetic_pdfs": args.synthetic, "workers": args.workers,
                          "serial_seconds": round(serial_seconds, 3), "parallel_cold_seconds": round(parallel_seconds, 3),
                          "speedup": round(serial_seconds / parallel_seconds, 2), "identical_results": equivalent}, indent=2))
        if not equivalent:
            raise SystemExit("Different results")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
