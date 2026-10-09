# -*- coding: utf-8 -*-
"""Document type: one decision point with a declared rule table.

Before this module the type was re-decided by three stacked overlays
(v0.12.6 ``_overlay``, v0.12.7 ``_retype``, v0.12.8 ``_retype``), each one
written against the output of the previous. Here the same rules live in one
table, :data:`TYPE_PASSES`, read top to bottom:

* a *pass* reads the current type once; inside a pass the first rule that
  applies decides and the pass ends;
* the next pass reads the type the previous one left.

The type coming in is the *base reading* (v0.12.5 plus the date-block
normalisation of v0.12.6): up to there the type is decided together with the
fields (journal/publisher split), and it stays there.

Every rule records its name in ``parser_notes`` and the previous type in
``type_candidates``. The behaviour is that of parser v0.12.8; the
equivalence is checked over the whole corpus (see
``reports/parser_doctype_refactor.md``). Rule changes after this refactor go
here, with their effect measured against the gold sample.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, FrozenSet, Optional, Tuple

from . import v12_5 as _v125
from . import v12_6 as _v126
from . import v12_7 as _v127
from . import v12_8 as _v128

#: A decision: new type, rule name and fields the rule also fixes.
Decision = Tuple[str, str, Dict[str, Any]]
_REPEATED_MARKER_RE = re.compile(r"^\s*(?:[○●•◦▪·*]\s*)?(?:-{2,}|_{2,}|–{2,}|—+)\s*[.,;:]?\s*")
_BULLET_RE = re.compile(r"^\s*[○●•◦▪·*\-]\s+")


@dataclass
class Context:
    text: str
    out: Dict[str, Any]
    _cache: Dict[str, str] = field(default_factory=dict)

    @property
    def body(self) -> str:
        """Text without a leading repeated-author marker."""
        if "body" not in self._cache:
            self._cache["body"] = _REPEATED_MARKER_RE.sub("", self.text)
        return self._cache["body"]

    @property
    def body_unbulleted(self) -> str:
        """Also without a leading list bullet."""
        if "unbulleted" not in self._cache:
            self._cache["unbulleted"] = _BULLET_RE.sub("", self.body)
        return self._cache["unbulleted"]


@dataclass(frozen=True)
class Rule:
    name: str
    #: Types the rule may start from (None: any). Checked before ``decide``.
    sources: Optional[FrozenSet[str]]
    decide: Callable[[Context, str], Optional[Decision]]
    doc: str = ""


@dataclass(frozen=True)
class Pass:
    name: str
    rules: Tuple[Rule, ...]


def _types(*names: str) -> FrozenSet[str]:
    return frozenset(names)


def _is_thesis(body: str) -> bool:
    return bool(_v126._THESIS_EVIDENCE_RE.search(body) or _v127._THESIS_EXTRA_RE.search(body))


# --- pass 1-3: title words, labels and containers (v0.12.6) ---------------

def _thesis_word_in_title(ctx: Context, ptype: str) -> Optional[Decision]:
    title = _v126._clean(ctx.out.get("title"))
    if not _v126._TITLE_THESIS_WORD_RE.search(title):
        return None
    outside = ctx.text.replace(title, " ", 1) if title else ctx.text
    if _v126._THESIS_EVIDENCE_RE.search(outside) or _v126._THESIS_EVIDENCE_RE.search(title):
        return None
    new = "conference_paper" if _v126._CONFERENCE_RE.search(outside) else "libro"
    return new, "v126_thesis_word_in_title_only", {}


def _ponencia_label(ctx: Context, ptype: str) -> Optional[Decision]:
    if ptype in {"conference_paper", "tesis"} or not _v126._PONENCIA_RE.search(ctx.text):
        return None
    return "conference_paper", "v126_explicit_ponencia_label", {}


def _chapter_container(ctx: Context, ptype: str) -> Optional[Decision]:
    if not _v126._chapter_container(ctx.out, ctx.text):
        return None
    fixes = {"journal": None} if ptype == "articulo_revista" else {}
    return "capitulo_libro", "v126_chapter_container_with_editor_or_pages", fixes


def _title_and_publisher(ctx: Context, ptype: str) -> Optional[Decision]:
    if not _v126._title_and_publisher_only(_v126._LIST_MARKER_RE.sub("", ctx.text)):
        return None
    return "libro", "v126_title_and_publisher_book", {}


# --- pass 4: explicit bibliographic evidence (v0.12.7) --------------------

def _unpublished(ctx: Context, ptype: str) -> Optional[Decision]:
    body = ctx.body
    if not _v127._UNPUBLISHED_RE.search(body):
        return None
    # An unpublished thesis is a thesis; one read at a colloquium is a conference paper.
    if _is_thesis(body):
        return "tesis", "v127_thesis_statement", {}
    if _v127._EVENT_RE.search(body):
        return "conference_paper", "v127_unpublished_event", {}
    return "material_inedito", "v127_unpublished_material", {}


def _serial_container_online(ctx: Context, ptype: str) -> Optional[Decision]:
    serial = _v127._SERIAL_CONTAINER_RE.search(ctx.body)
    # «…en la revista El Gráfico» inside a title is prose: the container must read «En Revista…».
    if not (serial and serial.group(0)[:1] in "EI" and serial.group("journal")[:1].isupper()):
        return None
    return "articulo_revista", "v127_serial_container_online", {"journal": serial.group("journal").split(",")[0].strip(" .:")}


def _journal_number_pages(ctx: Context, ptype: str) -> Optional[Decision]:
    body = ctx.body
    serial = _v127._SERIAL_CONTAINER_RE.search(body)
    numbered = _v127._JOURNAL_NUMBER_PAGES_RE.search(body)
    journal = None
    if serial:
        journal = serial.group("journal").split(",")[0].strip(" .:")
    elif (numbered and not re.search(r"\b(?:En|In)\s*:?\s", body[: numbered.start() + 1])
          and not _v127._EDITION_NOTE_RE.search(body) and not _v127._CITY_COLON_RE.search(body)):
        journal = numbered.group("journal").strip(" .:")
    if not journal:
        return None
    return "articulo_revista", "v127_journal_number_pages", {
        "journal": journal, "publisher": None, "publisher_observed": None, "source_publisher": None}


def _thesis_statement(ctx: Context, ptype: str) -> Optional[Decision]:
    # Thesis and event statements outrank a trailing «City, Institution».
    return ("tesis", "v127_thesis_statement", {}) if _is_thesis(ctx.body) else None


def _academic_event(ctx: Context, ptype: str) -> Optional[Decision]:
    return ("conference_paper", "v127_academic_event", {}) if _v127._EVENT_RE.search(ctx.body) else None


def _city_and_publisher(ctx: Context, ptype: str) -> Optional[Decision]:
    body = ctx.body
    book = _v127._CITY_PUBLISHER_END_RE.search(body)
    if not book or _v127._NOT_PUBLISHER_RE.match(book.group("publisher").strip()) or _v127._NOT_A_BOOK_RE.search(body):
        return None
    # «Título. En Obra colectiva. São Paulo. Educ.» is a chapter of that book.
    chapter = re.search(r"(?:^|[.,)]\s*)(?:En|In)\s*:?\s+[A-ZÁÉÍÓÚÑ]", body[: book.start() + 1])
    return ("capitulo_libro" if chapter else "libro"), "v127_city_and_publisher", {"publisher": book.group("publisher").strip()}


# --- pass 5: norms, loose chapters, reports, dated web pieces (v0.12.8) ----

def _legal(ctx: Context, ptype: str) -> Optional[Decision]:
    rule = _v128._legal(ctx.body_unbulleted, ptype)
    return ("documento_legal", rule, {"journal": None}) if rule else None


def _loose_chapter(ctx: Context, ptype: str) -> Optional[Decision]:
    if not _v128._loose_chapter(ctx.body_unbulleted):
        return None
    return "capitulo_libro", "v128_chapter_container_after_question_or_missing_period", {}


def _public_body_report(ctx: Context, ptype: str) -> Optional[Decision]:
    body = ctx.body_unbulleted
    head, rest = _v128._head_before_date(body), _v128._rest_after_date(body)
    if not (_v128._PUBLIC_BODY_RE.match(head.strip()) and _v128._DATA_REPORT_RE.search(rest[:160])):
        return None
    return "informe_documento", "v128_public_body_data_report", {}


def _dated_news_online(ctx: Context, ptype: str) -> Optional[Decision]:
    body = ctx.body_unbulleted
    if not (ctx.out.get("has_url") and _v128._DAY_MONTH_DATE_RE.search(body[:260])
            and _v128._NEWS_OUTLET_RE.search(_v128._rest_after_date(body))):
        return None
    return "material_web", "v128_dated_news_piece_online", {"publisher": None}


_BOOKISH = _types("libro", "sin_clasificar")
_ANY_BUT_STRONG = None  # _legal checks its own exclusions (tesis, capitulo_libro, documento_legal)

#: The declared order. Read it as: which evidence may overturn which reading.
TYPE_PASSES: Tuple[Pass, ...] = (
    Pass("palabra_tesis_en_titulo", (
        Rule("thesis_word_in_title_only", _types("tesis"), _thesis_word_in_title,
             "«tesis» solo dentro del título no es una tesis: libro, o ponencia si hay evento"),
    )),
    Pass("rotulo_ponencia", (
        Rule("explicit_ponencia_label", None, _ponencia_label, "«[Ponencia]», «[Comunicación]»… → ponencia"),
    )),
    Pass("contenedor", (
        Rule("chapter_container", _types("libro", "sin_clasificar", "articulo_revista"), _chapter_container,
             "«. En / , en <obra>» con rol de editor, páginas o nombres de editores → capítulo"),
        Rule("title_and_publisher", _types("sin_clasificar"), _title_and_publisher,
             "«Título. Editorial.» → libro"),
    )),
    Pass("evidencia_explicita", (
        Rule("unpublished", _types("sin_clasificar", "libro", "material_web", "informe_documento"), _unpublished,
             "«Inédito / no publicado» → material inédito, salvo tesis o evento"),
        Rule("serial_container_online", _types("material_web"), _serial_container_online,
             "«En Revista/Anuario…» con URL → artículo (la URL es acceso)"),
        Rule("journal_number_pages", _BOOKISH, _journal_number_pages,
             "«Revista, n. pp. x-y» o «En: Anuario…» → artículo"),
        Rule("thesis_statement", _types("sin_clasificar"), _thesis_statement, "grado académico explícito → tesis"),
        Rule("academic_event", _types("sin_clasificar"), _academic_event, "congreso, jornada, reunión… → ponencia"),
        Rule("city_and_publisher", _types("sin_clasificar"), _city_and_publisher,
             "«Ciudad, Editorial.» → libro, o capítulo si antes hay «En <obra>»"),
    )),
    Pass("norma_capitulo_informe_web", (
        Rule("legal", _ANY_BUT_STRONG, _legal, "norma numerada, código o reglamento de un organismo → documento legal"),
        Rule("loose_chapter", _BOOKISH, _loose_chapter, "«¿…? En E. Editor (Comp.)… (pp.)» → capítulo"),
        Rule("public_body_report", _BOOKISH, _public_body_report, "organismo público + datos → informe"),
        Rule("dated_news_online", _BOOKISH, _dated_news_online, "pieza fechada de un medio, en URL → web"),
    )),
)


def decide_type(text: str, out: Dict[str, Any]) -> Dict[str, Any]:
    """Apply :data:`TYPE_PASSES` to a base reading, in place, and return it."""
    ctx = Context(text, out)
    for type_pass in TYPE_PASSES:
        ptype = out.get("publication_type") or "sin_clasificar"
        for rule in type_pass.rules:
            if rule.sources is not None and ptype not in rule.sources:
                continue
            decision = rule.decide(ctx, ptype)
            if decision is None:
                continue
            new_type, note, fixes = decision
            _v126._set_type(out, new_type, note)
            out.update(fixes)
            break
    return out


def rule_table() -> list:
    """The table as rows, for reports and the UI."""
    return [{"pass": p.name, "order": i + 1, "rule": r.name,
             "sources": sorted(r.sources) if r.sources is not None else "cualquiera", "doc": r.doc}
            for p in TYPE_PASSES for i, r in enumerate(p.rules)]


__all__ = ["TYPE_PASSES", "Pass", "Rule", "decide_type", "rule_table"]
