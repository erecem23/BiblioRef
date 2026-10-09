# -*- coding: utf-8 -*-
"""CLI del sidecar derivado.

    python -m biblioref.derived sync
    python -m biblioref.derived stats
    python -m biblioref.derived resolve --limit 200 --rate 2
    python -m biblioref.derived decide
    python -m biblioref.derived progress

``resolve`` es la única orden que sale a la red. Se puede cortar con Ctrl-C en
cualquier momento: cada respuesta se guarda apenas llega y la próxima corrida
retoma donde quedó.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .batch import (
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_RATE_PER_SECOND,
    build_backends,
    decide_pending,
    fetch_missing,
    pending_queries,
    resolution_progress,
)
from .analysis import full_report
from .sync import corpus_stats, default_project_file, default_store_path, open_store, sync_from_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BiblioRef derived analysis store")
    parser.add_argument("command", choices=("sync", "stats", "resolve", "decide", "progress", "report"))
    parser.add_argument("--project-file", type=Path, default=None, help="project.json de origen")
    parser.add_argument("--store", type=Path, default=None, help="archivo sqlite destino")
    parser.add_argument("--limit", type=int, default=None, help="máximo de consultas/referencias a procesar")
    parser.add_argument("--docs", default=None, help="lista de doc_id separados por coma")
    parser.add_argument("--rate", type=float, default=DEFAULT_RATE_PER_SECOND,
                        help="consultas por segundo (default %(default)s)")
    parser.add_argument("--backends", default="crossref,openalex", help="backends separados por coma")
    parser.add_argument("--email", default=None, help="mailto para el polite pool de Crossref")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--max-attempts", type=int, default=DEFAULT_MAX_ATTEMPTS)
    parser.add_argument("--retry-failed", action="store_true", help="reintentar consultas agotadas")
    parser.add_argument("--missing-doi", action="store_true",
                        help="solo referencias sin DOI del parser (donde la resolución puede aportar uno)")
    parser.add_argument("--redecide", action="store_true", help="recalcular decisiones ya tomadas (offline)")
    parser.add_argument("--no-decide", action="store_true", help="solo traer respuestas, no decidir")
    parser.add_argument("--dry-run", action="store_true", help="mostrar qué haría, sin salir a la red")
    parser.add_argument("--group-by", default="university",
                        help="university | program | faculty | thesis_year | director | degree_level")
    parser.add_argument("--out", type=Path, default=None, help="guardar el reporte como JSON")
    return parser


def _docs(args) -> list | None:
    return [d.strip() for d in args.docs.split(",") if d.strip()] if args.docs else None


def _dump(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "sync":
        print(f"origen : {args.project_file or default_project_file()}")
        print(f"destino: {args.store or default_store_path()}")
        conn, report = sync_from_file(args.project_file, args.store)
        _dump(report.as_dict())
        _dump(corpus_stats(conn))
        conn.close()
        return 0

    conn = open_store(args.store)
    try:
        if args.command == "stats":
            _dump(corpus_stats(conn))
            return 0

        if args.command == "report":
            report = full_report(conn, doc_ids=_docs(args), group_by=args.group_by)
            if args.out:
                args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"reporte guardado en {args.out}")
            else:
                _dump(report)
            return 0

        if args.command == "progress":
            _dump(resolution_progress(conn))
            return 0

        if args.command == "decide":
            _dump(decide_pending(conn, redecide=args.redecide, doc_ids=_docs(args), limit=args.limit).as_dict())
            _dump(resolution_progress(conn))
            return 0

        # resolve
        pending = pending_queries(
            conn,
            max_attempts=args.max_attempts,
            retry_failed=args.retry_failed,
            limit=args.limit,
            doc_ids=_docs(args),
            only_missing_doi=args.missing_doi,
        )
        backends = [b.strip() for b in args.backends.split(",") if b.strip()]
        requests = len(pending) * len(backends)
        eta_min = (len(pending) / args.rate / 60.0) if args.rate > 0 else 0.0
        print(f"consultas pendientes : {len(pending)}")
        print(f"backends             : {', '.join(backends)}")
        print(f"pedidos estimados    : {requests}")
        print(f"ritmo                : {args.rate}/s  ->  ~{eta_min:.0f} min")
        if args.dry_run:
            print("dry-run: no se hizo ningún pedido.")
            return 0

        def progress(done: int, total: int) -> None:
            if done % 50 == 0 or done == total:
                print(f"  {done}/{total}", flush=True)

        report = fetch_missing(
            conn,
            build_backends(
                names=backends,
                crossref_email=args.email,
                timeout=args.timeout,
            ),
            limit=args.limit,
            doc_ids=_docs(args),
            rate_per_second=args.rate,
            max_attempts=args.max_attempts,
            retry_failed=args.retry_failed,
            only_missing_doi=args.missing_doi,
            progress=progress,
        )
        _dump(report.as_dict())

        if not args.no_decide:
            _dump(decide_pending(conn, doc_ids=_docs(args)).as_dict())
        _dump(resolution_progress(conn))
        return 0
    except KeyboardInterrupt:
        print("\ninterrumpido; lo traído hasta acá quedó guardado.", file=sys.stderr)
        _dump(resolution_progress(conn))
        return 130
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
