# -*- coding: utf-8 -*-
"""BiblioRef parser legacy v0.1.

Adaptación modular del parser bibliográfico contenido en `extractor_v322.py`
(V3.2.2). La lógica de detección/segmentación de PDF NO se incluye aquí.
Este módulo recibe referencias ya individualizadas y extrae campos internos.

Objetivo: servir como baseline reproducible para desarrollar y validar el
módulo downstream de parsing de BiblioRef sin mezclarlo con el núcleo de
recuperación/segmentación.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd

PARSER_VERSION = "legacy-v3.2.2-adapted-v0.1"

PUBLISHER_RE = re.compile(
    r"\b("
    r"press|university press|academic press|oxford university press|cambridge university press|"
    r"routledge|springer|sage|wiley|elsevier|guilford press|manual moderno|"
    r"az editora|editorial teseo|american psychological association|apa books|"
    r"paid[oó]s|paidos|pearson"
    r")\b",
    flags=re.IGNORECASE,
)

REPOSITORY_RE = re.compile(
    r"\b("
    r"archivo digital|repositorio|repository|sedici|rdu|memoria acad[eé]mica|"
    r"facultad de|universidad nacional|universidad de|institute of education sciences|"
    r"u\.s\. department of education|national center for|centre for"
    r")\b",
    flags=re.IGNORECASE,
)

ARTICLE_CUE_RE = re.compile(
    r"(\b\d+\(\d+\)\b|\b\d{1,4}\s*[-–]\s*\d{1,4}\b|"
    r"(?:https?://(?:dx\.)?doi\.org/|doi\s*:?\s*)10\.\d{4,9}/)",
    flags=re.IGNORECASE,
)

REVISTA_CUE_RE_GLOBAL = re.compile(
    r"\b("
    r"journal|review|revista|anales|annals|proceedings|"
    r"psychology|psychiatry|oncology|medicine|medical|"
    r"behaviour|behavior|research|therapy|physiology|mapping|"
    r"neuroimage|cortex|brain|psychotherapy|"
    r"computers in human behavior|human brain mapping|"
    r"frontiers in|psycho-oncology|bmc research notes|"
    r"clinical|cognitive|salud|educación|educacion|clin"
    r")\b",
    flags=re.IGNORECASE,
)

AUTORES_VIP = {
    r"\bFreud\b": "Freud, S.",
    r"\bLacan\b": "Lacan, J.",
    r"\bKlappenbach\b": "Klappenbach, H.",
    r"\bPiñeda\b|\bPineda\b": "Piñeda, M.",
    r"\bV[iy]got[s]?k[iy]\b": "Vygotsky, L. S.",
    r"\bOMS\b|Organización Mundial": "OMS",
    r"\bOPS\b|Organización Panamer": "OPS",
    r"\bUNESCO\b": "UNESCO",
    r"\bUNICEF\b": "UNICEF",
    r"\bAPA\b|American Psychological": "American Psychological Association",
}


def candidato_no_es_revista(cand: str) -> bool:
    if not isinstance(cand, str):
        return True
    c = cand.strip()
    if not c:
        return True
    if PUBLISHER_RE.search(c):
        return True
    if REPOSITORY_RE.search(c):
        return True
    if len(c.split()) > 10:
        return True
    return False


def norm_autor(n: Any) -> Optional[str]:
    if pd.isna(n) or str(n).strip() in ("", "nan"):
        return None
    n = str(n).strip()
    if "|" in n:
        n = n.split("|")[0].strip().rstrip(",.")
    n = re.sub(r"\s*\[.*?\]", "", n).strip()
    if re.match(r"^[A-Z]\.\s*[A-Z]\.?$", n):
        return None
    n = re.sub(r"\s+", " ", n).strip().rstrip(";,. ")
    return n if len(n) > 2 else None


def norm_revista(r: Any) -> Optional[str]:
    if pd.isna(r) or str(r).strip() in ("", "nan"):
        return None
    r = str(r).strip().rstrip(".")
    r = re.sub(r"https?://\S+", "", r).strip()
    r = re.sub(r"(?i:doi\s*:?\s*10\.\S+)", "", r).strip()
    r = re.sub(r"\s+", " ", r)
    fixes = {
        "Jpn J Clin Oncol": "Jpn J Clin Oncol",
        "Psycho Oncology": "Psycho-Oncology",
        "Clinica Contemporánea": "Clínica Contemporánea",
        "Clínica Contemporanea": "Clínica Contemporánea",
    }
    return fixes.get(r, r)


def normalizar_autores(raw: str) -> Tuple[Optional[str], str]:
    if not raw:
        return None, ""
    raw = re.sub(r"^[\d\.\-\s\[\]]+", "", raw).strip()
    t = raw
    t = re.sub(r",\s*&\s*|\s+&\s+", "||", t)
    t = re.sub(r"\s+\by\b\s+|\s+\band\b\s+", "||", t, flags=re.I)
    t = re.sub(r"\.,\s+", ".||", t)
    t = re.sub(r"\b(et al\.?|eds?\.?|comps?\.?|dirs?\.?|orgs?\.?)\b", "", t, flags=re.I)
    lista = [a.strip(" ,.") for a in t.split("||") if len(a.strip()) > 2]
    limpios: List[str] = []
    for a in lista:
        vip = next((c for p, c in AUTORES_VIP.items() if re.search(p, a, re.I)), None)
        limpios.append(vip if vip else re.sub(r"\.([A-Z])", r". \1", a).strip())
    autor = norm_autor(limpios[0]) if limpios else None
    return autor, " | ".join(limpios)


def extraer_revista_rescate(texto: str) -> Optional[str]:
    if not isinstance(texto, str) or not texto.strip():
        return None
    t = re.sub(r"\s+", " ", texto).strip()
    if not ARTICLE_CUE_RE.search(t):
        return None
    t = re.split(
        r"(?:https?://(?:dx\.)?doi\.org/\S+|https?://\S+|doi\s*:?\s*10\.\S+)",
        t,
        maxsplit=1,
        flags=re.I,
    )[0].strip()
    patrones = [
        r"\)\.\s*(?P<titulo>.+?[\.!?])\s*(?P<revista>[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñüÜ&\-\.\s]{2,120}?),\s*\d+\s*\(\d+\)\s*,\s*\d{1,4}\s*[-–]\s*\d{1,4}\b",
        r"\)\.\s*(?P<titulo>.+?)\.\s*(?P<revista>[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñüÜ&\-\.\s]{2,120}?),\s*\d+\s*\(\d+\)\b",
        r"\)\.\s*(?P<titulo>.+?[\.!?])\s*(?P<revista>[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñüÜ&\-\.\s]{2,120}?),\s*\d{1,4}\s*[-–]\s*\d{1,4}\b",
        r"\)\.\s*(?P<titulo>.+?[\.!?])\s*(?P<revista>[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñüÜ&\-\.\s]{2,120}?),\s*\d+\s*,\s*\d{4,6}\b",
        r"\)\.\s*(?P<titulo>.+?[\.!?])\s*(?P<revista>[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñüÜ&\-\.\s]{2,120}?)\.\s*$",
        r"(?P<revista>(?:Jpn J Clin Oncol|Psycho-Oncology|Psychotherapy|Proceedings of the National Academy of Sciences|Cl[ií]nica Contempor[aá]nea|Nature Human Behaviour|Biological Psychiatry|Human Brain Mapping|Mental Health and Physical Activity|Computers in Human Behavior|Frontiers in Physiology|Psychology Research and Behavior Management|NeuroImage|BMC Research Notes|Cerebral Cortex|Brain))",
    ]
    for pat in patrones:
        m = re.search(pat, t, re.I)
        if m:
            cand = norm_revista(m.group("revista").strip().rstrip(".,;"))
            if cand and 4 <= len(cand) <= 120 and len(cand.split()) <= 12 and not candidato_no_es_revista(cand):
                return cand
    return None


def clasificar_documento(cita: str, revista_canonica: Optional[str] = None) -> str:
    r = str(cita or "")
    if re.search(r"\b(tesis|dissertation|trabajo final|trabajo de grado)\b", r, re.I):
        return "tesis"
    if re.search(r"\b(Congreso|Conferencia|Conference|Simposio|Symposium|Jornadas)\b", r, re.I):
        return "conferencia"
    if re.search(r"\b(Ley N|Decreto|Resolución|Resolucion|Boletín Oficial|Boletin Oficial)\b", r, re.I):
        return "documento_legal"
    if re.search(r"\b(En\s|In\s)[A-Z]", r) and re.search(r"\((?:Ed\.|Eds\.|Comp\.|Comps\.|Dir\.|Dirs\.)\)", r):
        return "capitulo"
    if revista_canonica and str(revista_canonica).strip() not in ("", "None", "nan") and not candidato_no_es_revista(str(revista_canonica)):
        return "articulo_revista"
    if re.search(r",\s*\d+\s*\(\d+\)\s*,\s*\d{1,4}", r):
        return "articulo_revista"
    if re.search(r",\s*\d+\s*\(\d+\)", r):
        return "articulo_revista"
    if re.search(r",\s*\d{1,4}\s*[-–]\s*\d{1,4}\b", r):
        return "articulo_revista"
    if re.search(r",\s*\d+\s*,\s*\d{4,6}\b", r):
        return "articulo_revista"
    if re.search(r"10\.\d{4,9}/", r) and REVISTA_CUE_RE_GLOBAL.search(r):
        return "articulo_revista"
    if re.search(r"\b(Universidad|University|Institute|Instituto|Department of|Departamento de|Ministry|Ministerio|National Center|Institute of Education Sciences|U\.S\. Department of Education)\b", r, re.I):
        return "documento_institucional"
    if re.search(r"\b(Paidós|Siglo XXI|Amorrortu|Nueva Visión|Gedisa|Herder|Springer|Wiley|Oxford|Cambridge|Guilford|Erlbaum|Sage|Routledge|Pearson|Fondo de Cultura|Alianza|Anagrama|Planeta|Manantial|Biblos|Katz|Morata|Trotta|Ariel|Lumen|Granica)\b", r, re.I):
        return "libro"
    if re.search(r"https?://|www\.", r, re.I):
        return "recurso_web"
    return "sin_clasificar"


def titulo_y_fuente(cita: str, tipo: str) -> Tuple[str, str]:
    resto = re.sub(
        r"^([^(]+)\(\s*((?:19|20)\d{2}[a-z]?(?:/[12]\d{3}[a-z]?)?|s\.f\.)[^)]*\)\s*\.?",
        "",
        str(cita or ""),
        flags=re.I,
    )
    resto = re.sub(r"\s+", " ", resto).strip()
    resto = re.split(
        r"(?:https?://(?:dx\.)?doi\.org/\S+|https?://\S+|doi\s*:?\s*10\.\S+)",
        resto,
        maxsplit=1,
        flags=re.I,
    )[0].strip()
    if tipo == "articulo_revista":
        patrones = [
            r"^(?P<titulo>.+?[\.!?])\s*(?P<revista>[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñüÜ&\-\.\s]{2,120}?),\s*\d+\s*\(\d+\)\s*,\s*\d{1,4}\s*[-–]\s*\d{1,4}\b",
            r"^(?P<titulo>.+?)\.\s*(?P<revista>[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñüÜ&\-\.\s]{2,120}?),\s*\d+\s*\(\d+\)\b",
            r"^(?P<titulo>.+?[\.!?])\s*(?P<revista>[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñüÜ&\-\.\s]{2,120}?),\s*\d{1,4}\s*[-–]\s*\d{1,4}\b",
            r"^(?P<titulo>.+?[\.!?])\s*(?P<revista>[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñüÜ&\-\.\s]{2,120}?),\s*\d+\s*,\s*\d{4,6}\b",
            r"^(?P<titulo>.+?[\.!?])\s*(?P<revista>[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñüÜ&\-\.\s]{2,120}?)\.\s*$",
        ]
        for pat in patrones:
            m = re.search(pat, resto, re.I)
            if m:
                titulo = m.group("titulo").strip()
                titulo = titulo.rstrip() if titulo.endswith(("?", "!")) else titulo.rstrip(". ")
                revista = norm_revista(m.group("revista").strip().rstrip(".,;"))
                if revista and not candidato_no_es_revista(revista):
                    return titulo, revista
    partes = re.split(r"[\.!?]\s+", resto, maxsplit=1)
    titulo = partes[0].strip().rstrip(". ")
    fuente = partes[1].strip() if len(partes) > 1 else ""
    fuente = re.sub(r"https?://\S+", "", fuente).strip()
    fuente = re.sub(r"(?i:doi\s*:\s*10\.\S+)", "", fuente).strip()
    return titulo, fuente


def parse_reference(texto: str) -> Dict[str, Any]:
    """Parsea una referencia ya individualizada usando la lógica heredada V3.2.2."""
    texto = re.sub(r"\s+", " ", str(texto or "")).strip()
    m = re.search(
        r"^([^(]+)\(\s*((?:19|20)\d{2}[a-z]?(?:/[12]\d{3}[a-z]?)?|s\.f\.)[^)]*\)\s*\.?",
        texto,
        re.I,
    )
    if m:
        auts_raw = m.group(1).strip()
        anio = m.group(2).strip()
    else:
        anios = re.findall(r"\b(?:18|19|20)\d{2}\b", texto)
        anio = anios[0] if anios else ""
        auts_raw = ""

    revista = extraer_revista_rescate(texto)
    tipo = clasificar_documento(texto, revista_canonica=revista)
    titulo, fuente = titulo_y_fuente(texto, tipo)
    autor, autores_norm = normalizar_autores(auts_raw)

    if tipo == "articulo_revista" and revista:
        fuente = revista

    md = re.search(r"(10\.\d{4,9}/[^\s\"<>]+)", texto, re.I)
    doi = md.group(1).rstrip(".,)") if md else None

    return {
        "parser_version": PARSER_VERSION,
        "autor_final": autor,
        "autores_normalizados": autores_norm,
        "anio_edicion": anio,
        "tipo_documento": tipo,
        "es_revista": tipo == "articulo_revista",
        "titulo": titulo,
        "revista_canonica": revista if tipo == "articulo_revista" else None,
        "revista_norm": revista.lower() if tipo == "articulo_revista" and revista else None,
        "fuente_editorial": fuente if tipo != "articulo_revista" else None,
        "doi": doi,
        "cita_cruda": texto,
    }


def parse_records(records: Sequence[Dict[str, Any]], text_key: str = "reference_text") -> List[Dict[str, Any]]:
    """Añade campos parseados a records de BiblioRef preservando los campos originales."""
    out: List[Dict[str, Any]] = []
    for rec in records:
        row = dict(rec)
        parsed = parse_reference(str(row.get(text_key, "") or ""))
        row.update(parsed)
        out.append(row)
    return out


def parse_dataframe(df: pd.DataFrame, text_col: str = "reference_text") -> pd.DataFrame:
    parsed = pd.DataFrame([parse_reference(x) for x in df[text_col].fillna("").astype(str)])
    base = df.reset_index(drop=True).copy()
    # Evita duplicar la columna textual cuando la entrada ya la contiene.
    if "cita_cruda" in base.columns:
        base = base.drop(columns=["cita_cruda"])
    return pd.concat([base, parsed], axis=1)


def main() -> int:
    ap = argparse.ArgumentParser(description="Parser bibliográfico legacy V3.2.2 adaptado para salidas BiblioRef")
    ap.add_argument("input_csv", help="CSV con referencias ya segmentadas")
    ap.add_argument("output_csv", help="CSV de salida con campos parseados")
    ap.add_argument("--text-col", default="reference_text", help="Columna con el texto completo de la referencia")
    ap.add_argument("--sep", default=",", help="Separador del CSV de entrada")
    ap.add_argument("--out-sep", default=",", help="Separador del CSV de salida")
    args = ap.parse_args()

    df = pd.read_csv(args.input_csv, sep=args.sep)
    if args.text_col not in df.columns:
        raise SystemExit(f"No existe la columna {args.text_col!r}. Columnas: {list(df.columns)}")
    out = parse_dataframe(df, text_col=args.text_col)
    Path(args.output_csv).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output_csv, index=False, sep=args.out_sep, encoding="utf-8-sig")
    print(f"OK: {len(out)} referencias -> {args.output_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
