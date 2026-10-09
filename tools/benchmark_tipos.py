"""Exactitud del tipo documental contra la muestra gold de 300 referencias.

    python tools/benchmark_tipos.py [--gold XLSX] [--out JSON] [--baseline JSON] [--solo-revisadas]

Mide exactitud, no cobertura: cada referencia queda como correcta, incorrecta
o sin clasificar frente a ``tipo_gold_v1`` (o ``tipo_gold_v0`` si la planilla
no tiene v1). Las filas marcadas ``EXCLUIDA`` no cuentan. Con ``--solo-revisadas`` cuenta
solo las filas cuya ``estado_revision`` ya no es «pendiente». Con
``--baseline`` lista las referencias cuyo tipo cambió respecto de otra corrida.

La muestra sale de tesis usadas para desarrollar las reglas: es control de
calidad, no evidencia held-out.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from biblioref.parsing import PARSER_VERSION, parse_reference  # noqa: E402

DEFAULT_GOLD = ROOT / "benchmarks" / "tipos_gold" / "BIBLIOREF_MUESTRA_300_TIPOS_GOLD_V1.xlsx"
UNCLASSIFIED = "sin_clasificar"


def load_gold(path: Path) -> list[dict]:
    import openpyxl

    sheet = openpyxl.load_workbook(path, read_only=True)["MUESTRA_300"]
    rows = list(sheet.iter_rows(values_only=True))
    header = [str(h) for h in rows[0]]
    return [dict(zip(header, r)) for r in rows[1:] if r and r[0]]


def verdict(predicted: str, gold: str) -> str:
    if predicted == UNCLASSIFIED:
        return "sin_clasificar"
    return "correcta" if predicted == gold else "incorrecta"


def run(gold_rows: list[dict], only_reviewed: bool) -> dict:
    rows = []
    for g in gold_rows:
        gold = g.get("tipo_gold_v1") or g.get("tipo_gold_v0")
        if gold == "EXCLUIDA":
            continue
        if only_reviewed and str(g.get("estado_revision") or "").strip().lower() == "pendiente":
            continue
        parsed = parse_reference(str(g["referencia_texto"]))
        predicted = parsed["publication_type"]
        rule = [n for n in str(parsed.get("parser_notes") or "").split(";") if n.startswith(("v126_", "v127_", "v128_"))]
        rows.append({
            "id": g["id_muestra"], "tesis": g["tesis"], "gold": gold, "tipo": predicted,
            "veredicto": verdict(predicted, gold), "regla": rule[-1] if rule else "",
            "confianza_gold": g.get("confianza_gold_v0"), "estado_revision": g.get("estado_revision"),
            "texto": str(g["referencia_texto"])[:200],
        })
    totals = collections.Counter(r["veredicto"] for r in rows)
    by_type = collections.defaultdict(collections.Counter)
    for r in rows:
        by_type[r["gold"]][r["veredicto"]] += 1
    confusion = collections.Counter(f"{r['gold']} -> {r['tipo']}" for r in rows if r["veredicto"] != "correcta")
    return {
        "parser_version": PARSER_VERSION, "n": len(rows), "solo_revisadas": only_reviewed,
        "totales": {k: totals.get(k, 0) for k in ("correcta", "incorrecta", "sin_clasificar")},
        "por_tipo_gold": {k: dict(v) for k, v in sorted(by_type.items())},
        "confusiones": dict(confusion.most_common()),
        "filas": rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--baseline", type=Path)
    ap.add_argument("--solo-revisadas", action="store_true")
    args = ap.parse_args()
    result = run(load_gold(args.gold), args.solo_revisadas)
    t = result["totales"]
    print(f"{result['parser_version']} · n={result['n']} · correctas {t['correcta']} · "
          f"incorrectas {t['incorrecta']} · sin clasificar {t['sin_clasificar']}")
    for pair, n in result["confusiones"].items():
        print(f"  {n:3d}  {pair}")
    if args.baseline:
        before = {r["id"]: r for r in json.loads(args.baseline.read_text(encoding="utf-8"))["filas"]}
        changed = [r for r in result["filas"] if r["id"] in before and before[r["id"]]["tipo"] != r["tipo"]]
        print(f"cambios de tipo vs baseline: {len(changed)}")
        for r in changed:
            print(f"  {r['id']} {before[r['id']]['tipo']} -> {r['tipo']} (gold {r['gold']}) {r['texto'][:90]}")
    if args.out:
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
