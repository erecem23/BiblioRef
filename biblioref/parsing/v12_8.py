# -*- coding: utf-8 -*-
"""BiblioRef downstream metadata parser v0.12.8.

Overlay on v0.12.7 from a stable-control case (hanging-indent APA list whose
extraction was already correct). Only the document type moves:

* a norm is a norm whatever the medium: «Decreto 297/2020. (…). Boletín
  Oficial…», «(…). Resolución n.º 1956.», «Reglamento para…» →
  ``documento_legal`` (the Boletín Oficial is where it was published, not a
  journal, and a URL is only how it is reached);
* «… cualitativos En I. Vasilachis (Coord.). Obra (pp. 239-271)» and
  «…¿presente fragmentario? En E. De la Garza…» are chapters: the container
  marker may follow «?» or a title that lost its period, as long as editor
  names and an editor role or page range follow;
* a public body reporting data («Dirección General… (2019). El estado de la
  escuela. Datos e indicadores») → ``informe_documento``;
* a dated piece («(2020, 12 de noviembre)») from a news agency or outlet, read
  at a URL → ``material_web``.

``has_url`` records the access medium separately from the type.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Sequence

from . import v12_5 as _v125
from . import v12_6 as _v126
from . import v12_7 as _v127

PARSER_VERSION = "biblioref-parser-v0.12.8"
PARSER_SCHEMA_VERSION = 12
PARSER_STATUS = "development_candidate"

_URL_RE = re.compile(r"https?://|www\.", re.I)

# --- documento_legal -------------------------------------------------------
_NORM_WORD = (
    r"(?:Decreto(?:\s+de\s+necesidad\s+y\s+urgencia|\s+ley|\s+reglamentario)?|DNU|Ley|Resoluci[oó]n|Disposici[oó]n|"
    r"Ordenanza|Acordada|Circular|Decreto-Ley|Decree|Act|Law)"
)
_NORM_NUMBER = r"(?:(?:\s+[A-Z]{2,6})?\s+(?:n[°º.]?\s*[°º]?|nro\.?|no\.|n[uú]mero)?\s*\d[\d./\-]*)"
#: «Decreto 297/2020», «Resolución n.º 1956», «Ley N° 26.206», «Ley 26206».
_NORM_WITH_NUMBER_RE = re.compile(rf"^\s*{_NORM_WORD}{_NORM_NUMBER}\b", re.I)
#: Codes and regulations are norms even without a number: «Reglamento para las Escuelas…».
_NORM_TITLE_RE = re.compile(r"^\s*(?:Reglamento|Estatuto|C[óo]digo|Constituci[óo]n)\b(?!\s+de\s+(?:[ée]tica\s+)?(?:la\s+)?(?:investigaci|conducta))", re.I)
#: «Bleichmar, S.», «Herrera, M., Caramelo, G.»: surname, comma, initial.
_PERSONAL_AUTHOR_RE = re.compile(r"[A-ZÁÉÍÓÚÑ][\wáéíóúñü'’\-]+,\s*[A-ZÁÉÍÓÚÑ]\.")
_OFFICIAL_GAZETTE_RE = re.compile(r"\bBolet[ií]n\s+Oficial\b|\bOfficial\s+Gazette\b|\bDiario\s+Oficial\b|\bRegistro\s+Oficial\b", re.I)
#: Journal evidence that a text about a law is an article about it.
_ISSUE_PAGES_RE = re.compile(r"\b\d+\s*\(\s*[\w.\-]+\s*\)\s*,\s*\d+\s*[-–]\s*\d+|\bpp?\.\s*\d+\s*[-–]\s*\d+|\bdoi\b|10\.\d{4,9}/", re.I)

# --- capitulo_libro ----------------------------------------------------------
#: «…fragmentario? En E. …», «…cualitativos En I. Vasilachis…»: a capital «En/In»
#: after «?», «!» or straight after a lowercase word.
#: «I. Vasilachis de Giardino (Coord.)», «E. De la Garza Toledo y J. C. Neffa»: initials,
#: then a surname that may carry particles, then «,», «y», «&» or «(».
_EDITOR_NAMES_RE = re.compile(
    r"^(?:[A-ZÁÉÍÓÚÑ]\.\s*(?:-\s*)?){1,3}"
    r"(?:(?:de|del|la|las|los|van|von|da|do|dos|di|le)\s+|[A-ZÁÉÍÓÚÑ][\wáéíóúñü'’\-]+\s*){1,5}"
    r"(?:,|\by\b|\band\b|&|\()"
)
_LOOSE_CONTAINER_RE = re.compile(r"(?:[?!]\s+|(?<=[a-záéíóúñü])\s+)(?:En|In):?\s+(?P<container>.+)$")

# --- informe_documento -------------------------------------------------------
_PUBLIC_BODY_RE = re.compile(
    r"^(?:Direcci[oó]n|Secretar[ií]a|Subsecretar[ií]a|Ministerio|Ministry|Consejo|Instituto\s+Nacional|"
    r"Defensor[ií]a|Agencia|Oficina|Departamento|Department|Gobierno|Government|Observatorio|"
    r"INDEC|UNESCO|UNICEF|OIT|ILO|OMS|OPS|CEPAL|Banco\s+Mundial|World\s+Bank)\b"
)
_DATA_REPORT_RE = re.compile(
    r"\b(?:datos\s+e\s+indicadores|indicadores|estad[ií]sticas?|relevamiento|anuario\s+estad[ií]stico|censo|"
    r"encuesta\s+(?:nacional|permanente|provincial)|informe|reporte|diagn[óo]stico\s+(?:de\s+situaci[oó]n|institucional))\b",
    re.I,
)

# --- material_web -----------------------------------------------------------
#: «(2020, 12 de noviembre)»: a day-and-month date is the mark of a dated piece.
_DAY_MONTH_DATE_RE = re.compile(
    r"\(\s*(?:18|19|20)\d{2}\s*,\s*(?:\d{1,2}\s+de\s+)?(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
    r"septiembre|setiembre|octubre|noviembre|diciembre|january|february|march|april|may|june|july|august|"
    r"september|october|november|december)\b",
    re.I,
)
_NEWS_OUTLET_RE = re.compile(
    r"\b(?:Agencia\s+de\s+Noticias|Noticias|Diario|Peri[óo]dico|Semanario|Portal|Blog|News|Newspaper|Prensa|"
    r"P[áa]gina\s*(?:12|/12)|Clar[ií]n|La\s+Naci[oó]n|Infobae|El\s+Pa[ií]s|Telam|T[ée]lam)\b"
)


def _rest_after_date(text: str) -> str:
    m = _v125._APA_RE.match(text)
    return m.group("rest") if m else text


def _head_before_date(text: str) -> str:
    m = _v125._APA_RE.match(text)
    return m.group("head") if m else ""


def _legal(text: str, ptype: str) -> str:
    """The rule that makes this a norm, or ''."""
    if ptype in {"tesis", "capitulo_libro", "documento_legal"}:
        return ""
    head, rest = _head_before_date(text), _rest_after_date(text)
    if _ISSUE_PAGES_RE.search(text):
        return ""
    if _NORM_WITH_NUMBER_RE.match(head) or _NORM_WITH_NUMBER_RE.match(text):
        return "v128_legal_norm_in_author_slot"
    if _NORM_WITH_NUMBER_RE.match(rest):
        return "v128_legal_norm_in_title_slot"
    # «Bleichmar, S. (2005). Estatuto de lo histórico…», «Herrera, M. (2015). Código Civil… comentado»:
    # a person writing about a code or with that word in a title is a book. A code is issued by a body.
    if (_NORM_TITLE_RE.match(rest) and ptype in {"sin_clasificar", "libro", "material_web", "informe_documento"}
            and not _PERSONAL_AUTHOR_RE.search(head) and not re.search(r"\bcomentad[oa]s?\b", rest[:160], re.I)):
        return "v128_legal_code_or_regulation_title"
    if _OFFICIAL_GAZETTE_RE.search(rest) and ptype in {"articulo_revista", "sin_clasificar", "libro"} and _NORM_WITH_NUMBER_RE.search(text):
        return "v128_legal_official_gazette"
    return ""


def _loose_chapter(text: str) -> bool:
    rest = _rest_after_date(text)
    m = _LOOSE_CONTAINER_RE.search(rest[:400])
    if not m or m.start() < 8:
        return False
    container = m.group("container")
    if _v126._JOURNAL_CONTAINER_RE.search(container[:160]) or _v126._JOURNAL_CONTAINER_RE.search(rest[: m.start()]):
        return False
    # Without the period, the container itself must read as an edited work.
    return bool(
        (_v126._EDITOR_NAMES_RE.match(container) or _EDITOR_NAMES_RE.match(container))
        and (_v126._EDITOR_ROLE_RE.search(container[:240]) or _v126._PAGE_RANGE_RE.search(container[:260]))
    )


def _retype(text: str, out: Dict[str, Any]) -> None:
    ptype = out.get("publication_type") or "sin_clasificar"
    body = re.sub(r"^\s*(?:[○●•◦▪·*]\s*)?(?:-{2,}|_{2,}|–{2,}|—+)\s*[.,;:]?\s*", "", text)
    body = re.sub(r"^\s*[○●•◦▪·*\-]\s+", "", body)

    rule = _legal(body, ptype)
    if rule:
        _v126._set_type(out, "documento_legal", rule)
        out["journal"] = None
        return

    if ptype in {"libro", "sin_clasificar"} and _loose_chapter(body):
        _v126._set_type(out, "capitulo_libro", "v128_chapter_container_after_question_or_missing_period")
        return

    head, rest = _head_before_date(body), _rest_after_date(body)
    title_zone = rest[:160]
    if (ptype in {"libro", "sin_clasificar"} and _PUBLIC_BODY_RE.match(head.strip())
            and _DATA_REPORT_RE.search(title_zone)):
        _v126._set_type(out, "informe_documento", "v128_public_body_data_report")
        return

    if (ptype in {"libro", "sin_clasificar"} and out.get("has_url") and _DAY_MONTH_DATE_RE.search(body[:260])
            and _NEWS_OUTLET_RE.search(rest)):
        _v126._set_type(out, "material_web", "v128_dated_news_piece_online")
        out["publisher"] = None


def parse_reference(texto: str) -> Dict[str, Any]:
    text = _v127._clean(texto)
    out = _v127.parse_reference(text)
    out["has_url"] = bool(_URL_RE.search(text))
    _retype(text, out)
    style = str(out.get("parse_style") or "")
    if "v128" not in style:
        out["parse_style"] = "+".join(x for x in (style, "v128_legal_chapter_report_web") if x)
    out["parser_version"] = PARSER_VERSION
    out["schema_version"] = PARSER_SCHEMA_VERSION
    out["parser_status"] = PARSER_STATUS
    return out


def parse_records(records: Sequence[Dict[str, Any]], text_key: str = "reference_text") -> List[Dict[str, Any]]:
    output: List[Dict[str, Any]] = []
    for rec in records:
        row = dict(rec)
        row["parsed"] = parse_reference(str(row.get(text_key, "") or ""))
        output.append(row)
    return output


def flatten_parsed(parsed: Dict[str, Any] | None, prefix: str = "parsed_") -> Dict[str, Any]:
    return _v127.flatten_parsed(parsed, prefix=prefix)
