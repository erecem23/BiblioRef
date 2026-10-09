# -*- coding: utf-8 -*-
"""Benchmark del consolidado «últimas tesis, antes/después».

Corre ``biblioref.pipeline.process_pdf`` sobre los casos de
``benchmarks/consolidado_v0_1/cases.json`` (20 tesis de selected20 y las tres
tesis nuevas con salida referencia a referencia) y mide la *forma* de la
segmentación, no sólo el conteo:

- registros, zonas, caracteres totales;
- segmentos muy cortos (< 5 palabras) y muy largos (>= 140 y >= 500 palabras);
- DOI/URL/tails aislados (registro que es casi sólo un enlace o un «Recuperado de»);
- posibles fusiones: dos o más cabezas autor-año, o marcadores ``[n]`` internos;
- posibles fragmentos: registros que abren en minúscula o puntuación;
- contaminación narrativa: segmentos largos con densidad de palabras funcionales
  de prosa y casi sin años;
- estado del shadow adaptativo y zonas en revisión (el análogo vivo de la
  cuarentena de zonas de 0.8.9).

Para las tesis con filas de la salida vieja, mide además cuántas de esas
referencias siguen apareciendo (recall textual) y cuántas abren un registro
(acuerdo de segmentación). No es ground truth: la salida vieja tiene sus propios
errores (T0009 trae filas con varias referencias ``[n]`` pegadas).

    python tools/benchmark_consolidado.py --out benchmarks/consolidado_v0_1/baseline.json
    python tools/benchmark_consolidado.py --out nuevo.json --baseline benchmarks/consolidado_v0_1/baseline.json
"""
from __future__ import annotations

import argparse
import concurrent.futures as futures
import hashlib
import json
import re
import sys
import time
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CASES = ROOT / "benchmarks" / "consolidado_v0_1" / "cases.json"

_YEAR_PAREN = re.compile(r"\(\s*(?:19|20)\d{2}[a-z]?\s*[),;]|\(s\.\s?f\.\)|\(n\.\s?d\.\)")
_YEAR = re.compile(r"\b(?:1[5-9]|20)\d{2}[a-z]?\b")
# Cabeza autor-año: «Apellido, I.» (o «Apellido, Nombre») seguido del año entre
# paréntesis a poca distancia. Contar cabezas dentro de un registro es la señal
# de fusión más barata y generalizable para estilos APA-like.
_HEAD = re.compile(
    r"(?:^|(?<=[.)\]]\s)|(?<=\.\s\s))"
    r"[A-ZÁÉÍÓÚÑÜ][A-Za-zÁÉÍÓÚÑÜáéíóúñüàèç'’\-]+(?:\s(?:de|del|van|von|y|&)?\s?[A-ZÁÉÍÓÚÑ][a-záéíóúñü'\-]+)?"
    r",\s(?:[A-ZÁÉÍÓÚÑ][a-záéíóúñ]*\.?\s?-?){1,4}[^()]{0,160}?\(\s*(?:19|20)\d{2}[a-z]?\s*\)"
)
_NUM_MARKER = re.compile(r"\[\d{1,3}\]")
_TAIL = re.compile(
    r"^\s*(?:https?://|www\.|doi\b|DOI\b|https?\s*:|Recuperado|Disponible|Retrieved|Available|"
    r"Consultado|Obtenido|\[?En\s+l[ií]nea\]?|URL\b|<?https?)",
    re.I,
)
_LINK = re.compile(r"(?:https?://\S+|www\.\S+|doi\s*:?\s*\S+|10\.\d{4,9}/\S+)", re.I)
_FUNCTION = set(
    "que de la el en y a los se del las por un una con no es su para como más pero sus le ya o "
    "este sí porque esta entre cuando muy sin sobre también me hasta hay donde quien desde todo "
    "nos durante todos uno les ni contra otros ese eso ante ellos e esto mí antes algunos qué unos "
    "yo otro otras otra él tanto esa estos mucho quienes nada muchos cual poco ella estar estas "
    "algunas algo nosotros lo al fue era ser son han ha puede pueden sea dicho decir cabe".split()
)


def _words(text: str) -> List[str]:
    return re.findall(r"[A-Za-zÁÉÍÓÚÑÜáéíóúñü]+", text)


def is_short(text: str) -> bool:
    return len(text.split()) < 5


def is_doi_tail(text: str) -> bool:
    words = text.split()
    if len(words) > 30:
        return False
    if _TAIL.match(text):
        return True
    stripped = _LINK.sub(" ", text)
    return bool(_LINK.search(text)) and len(_words(stripped)) <= 3


_CHAPTER_HOST = re.compile(r"^(?:En|In|Em|Dans|In:)\s")
_HEADER_INSIDE = re.compile(r"\b(?:REFERENCIAS(?:\s+BIBLIOGR[ÁA]FICAS)?|BIBLIOGRAF[ÍI]A(?:\s+GENERAL)?|REFERENCES|BIBLIOGRAPHY)\b")


def fusion_heads(text: str) -> int:
    # «En Apellido, I. (año)» es el libro que contiene un capítulo, no otra referencia.
    return sum(1 for m in _HEAD.finditer(text) if not _CHAPTER_HOST.match(m.group(0)))


def has_header_inside(text: str) -> bool:
    """Encabezado corrido de la bibliografía metido dentro de un registro."""
    return bool(_HEADER_INSIDE.search(text))


def internal_numeric_markers(text: str) -> int:
    return sum(1 for m in _NUM_MARKER.finditer(text) if m.start() > 4)


def is_possible_fusion(text: str) -> bool:
    return fusion_heads(text) >= 2 or internal_numeric_markers(text) >= 1


def is_fragment(text: str) -> bool:
    stripped = text.lstrip()
    if not stripped:
        return True
    first = stripped[0]
    if first.islower():
        return True
    return first in ",;:)]}.-–—" and not stripped.startswith(("—", "–", "-", "___"))


def narrative_score(text: str) -> float:
    words = [w.casefold() for w in _words(text)]
    if not words:
        return 0.0
    return sum(w in _FUNCTION for w in words) / len(words)


def is_narrative(text: str) -> bool:
    words = text.split()
    if len(words) < 80:
        return False
    years = len(_YEAR.findall(text))
    return narrative_score(text) >= 0.33 and years <= max(1, len(words) // 60)


def _norm(text: str) -> str:
    folded = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode().casefold()
    return re.sub(r"[^a-z0-9]+", "", folded)


def old_rows_agreement(old: List[str], texts: List[str]) -> Dict:
    """Recall textual y acuerdo de inicios contra filas de una salida anterior."""
    joined = _norm(" ".join(texts))
    starts = {_norm(t)[:40] for t in texts}
    found = opened = 0
    for row in old:
        key = _norm(row)[:40]
        if len(key) < 15:
            continue
        if key in joined:
            found += 1
        if key in starts:
            opened += 1
    usable = sum(1 for row in old if len(_norm(row)[:40]) >= 15)
    return {"old_rows": usable, "old_rows_found": found, "old_rows_open_a_record": opened}


def measure(texts: List[str]) -> Dict:
    n_words = [len(t.split()) for t in texts]
    return {
        "n_records": len(texts),
        "total_chars": sum(len(t) for t in texts),
        "short_lt5w": sum(is_short(t) for t in texts),
        "long_ge140w": sum(n >= 140 for n in n_words),
        "long_ge500w": sum(n >= 500 for n in n_words),
        "max_words": max(n_words) if n_words else 0,
        "doi_tail": sum(is_doi_tail(t) for t in texts),
        "possible_fusion": sum(is_possible_fusion(t) for t in texts),
        "numeric_fused": sum(internal_numeric_markers(t) >= 1 for t in texts),
        "possible_fragment": sum(is_fragment(t) for t in texts),
        "narrative": sum(is_narrative(t) for t in texts),
        "header_inside": sum(has_header_inside(t) for t in texts),
    }


def run_case(case: Dict) -> Dict:
    from biblioref.pipeline import process_pdf

    started = time.time()
    out = {"case": case["case"], "category": case["category"]}
    try:
        report = process_pdf(case["pdf"])
    except Exception as exc:  # noqa: BLE001 - se reporta
        out["error"] = f"{type(exc).__name__}: {exc}"
        return out
    texts = [str(r.get("reference_text") or "") for r in report.get("records", [])]
    shadow = report.get("adaptive_shadow") or {}
    decision = report.get("detection_decision") or {}
    out.update(measure(texts))
    out.update({
        "n_zones": report.get("n_zones"),
        "zones": [
            {
                "heading": str(z.get("heading") or "")[:60],
                "pages": f"{z.get('start_page')}-{z.get('end_page')}",
                "style": z.get("style"),
                "n_segments": z.get("n_segments"),
                "method": z.get("segmentation_method"),
            }
            for z in report.get("zones", [])
        ],
        "detection_method": decision.get("method"),
        "stable_output_preserved": decision.get("stable_output_preserved"),
        "shadow_status": shadow.get("overall_status"),
        "shadow_review_zones": len(shadow.get("review_zone_ids") or []),
        "page_boundaries_review": ((report.get("coverage_report") or {}).get("summary") or {}).get("n_page_boundaries_review"),
        "records_sha256": hashlib.sha256("\n".join(texts).encode("utf-8")).hexdigest(),
        "elapsed_s": round(time.time() - started, 1),
        "_texts": texts,
    })
    if case.get("old_references"):
        out.update(old_rows_agreement(case["old_references"], texts))
    return out


KEYS = [
    "n_records", "total_chars", "short_lt5w", "long_ge140w", "long_ge500w", "max_words",
    "doi_tail", "possible_fusion", "numeric_fused", "possible_fragment", "narrative",
    "header_inside", "n_zones", "shadow_review_zones", "page_boundaries_review",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--cases", default="", help="lista de casos separada por comas")
    parser.add_argument("--dump", type=Path, help="texto de cada registro por caso")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--remeasure", type=Path, nargs=2, metavar=("RESULT", "TEXTS"),
                        help="recalcular métricas desde una corrida guardada (json + --dump), sin PDFs")
    args = parser.parse_args()

    manifest = json.loads(CASES.read_text(encoding="utf-8"))
    wanted = {x.strip() for x in args.cases.split(",") if x.strip()}
    cases = [c for c in manifest["cases"] if not wanted or c["case"] in wanted]

    from biblioref.core.config import ALGORITHM_VERSION

    results: Dict[str, Dict] = {}
    if args.remeasure:
        saved = {r["case"]: r for r in json.loads(args.remeasure[0].read_text(encoding="utf-8"))["cases"]}
        saved_texts = json.loads(args.remeasure[1].read_text(encoding="utf-8"))
        by_case = {c["case"]: c for c in cases}
        for case_id, res in saved.items():
            if case_id not in by_case:
                continue
            texts = saved_texts.get(case_id, [])
            res.update(measure(texts))
            if by_case[case_id].get("old_references"):
                res.update(old_rows_agreement(by_case[case_id]["old_references"], texts))
            res["_texts"] = texts
            results[case_id] = res
        cases = [c for c in cases if c["case"] in results]
    with futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
        jobs = {pool.submit(run_case, c): c["case"] for c in cases if c["case"] not in results}
        for job in futures.as_completed(jobs):
            res = job.result()
            results[res["case"]] = res
            print(f"{res['case']:8s} {res.get('n_records', res.get('error'))}", flush=True)
    ordered = [results[c["case"]] for c in cases]
    texts = {r["case"]: r.pop("_texts", []) for r in ordered}
    version = json.loads(args.remeasure[0].read_text(encoding="utf-8"))["algorithm_version"] if args.remeasure else ALGORITHM_VERSION
    payload = {"algorithm_version": version, "cases": ordered}
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    if args.dump:
        args.dump.write_text(json.dumps(texts, ensure_ascii=False), encoding="utf-8")

    if args.baseline:
        base = {r["case"]: r for r in json.loads(args.baseline.read_text(encoding="utf-8"))["cases"]}
        print("\ncaso     categoria                          " + " ".join(k[:8] for k in KEYS))
        for r in ordered:
            b = base.get(r["case"], {})
            same = b.get("records_sha256") == r.get("records_sha256")
            cells = []
            for k in KEYS:
                before, after = b.get(k), r.get(k)
                cells.append(f"{after}" if before == after else f"{before}>{after}")
            print(f"{r['case']:8s} {r['category'][:34]:34s} {'=' if same else '*'} " + " ".join(cells))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
