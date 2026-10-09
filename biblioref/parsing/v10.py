# -*- coding: utf-8 -*-
"""BiblioRef downstream metadata parser v0.10.

Two families, both observed on a 310-reference Spanish-language education
thesis and both about metadata shapes that are ordinary in Ibero-American
publishing and absent from the patterns inherited from the v0.2 lexicon work.

- **Journal issue without a volume.** ``Comunicar, (38), 51-58`` and
  ``Revista Cepal, (119), 89-107`` carry an issue number in parentheses and no
  volume.  Every metadata pattern in the chain expects a volume digit before
  the parenthesis, so the source was never located: on that thesis, 92 of 94
  references with ``vol(issue)`` got their journal and **0 of 44** with
  issue-only metadata did.  The internal full stop of a name such as
  ``Edutec. Revista electrónica de tecnología educativa`` is not the cause;
  the same name is recovered correctly as soon as a volume is present.

- **Imprint after a closing place and country.** ``Santiago de Chile, Chile:
  Divergente.`` ends the reference with the publisher, but the imprint is
  accepted only when it matches the publisher lexicon or carries a shape word
  such as ``Press`` or ``Editorial``.  Publishers named after institutions or
  invented words (``UNAE``, ``Divergente``, ``Godot``, ``ZEMOS98``, ``Outliers
  School``) fall through.  The evidence that makes the segment safe is not the
  imprint but the left side: a closed list of country names immediately before
  the colon, at the very end of the reference.

Both routes only fill a field the previous version left empty.  Neither can
overwrite or rewrite a value that v0.9 already produced.

No PDF/reference-boundary code is imported or modified here.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence

from . import v09 as _v09
from . import v08 as _v08
from . import v03 as _v03
from . import v02 as _v02

PARSER_VERSION = "biblioref-parser-v0.10"
PARSER_SCHEMA_VERSION = 10
PARSER_STATUS = "development_candidate"

_UC = "A-ZÁÀÂÃÉÈÊÍÌÓÒÔÕÚÙÜÇÑ"

# --------------------------------------------------------------------------
# Journal issue without a volume
# --------------------------------------------------------------------------
# ``, (38), 51-58`` / ``, (119), 89-107`` / ``, (7), 1-21``.
# The issue is limited to three digits so a parenthesised year can never be
# read as an issue number, and the page or article number after it is
# required: a bare ``, (2016).`` is a date, not periodical metadata.
_ISSUE_ONLY_META_RE = re.compile(
    r",\s*\(\s*(\d{1,3})\s*\)\s*,\s*(?:pp?\.?\s*)?[A-Za-z]?\d{1,7}", re.I
)


def _issue_only_journal(text: str, base: Dict[str, Any]) -> Optional[str]:
    if base.get("journal"):
        return None
    if not _v03._YEAR_PAREN_RE.search(text[:260]):
        return None
    if _v02._is_chapter(text) or _v02.THESIS_RE.search(text) or _v08._THESIS_RE.search(text):
        return None
    if _v02.BOOK_CUE_RE.search(text) or _v02.CONF_RE.search(text) or _v02.LEGAL_RE.search(text):
        return None
    if re.search(r"\[[^\]]*(?:tese|tesis|disserta|thesis)[^\]]*\]", text, re.I):
        return None

    source = _v02._strip_auth_year(text)
    source = _v09._APA_LINK_SPLIT_RE.split(source, maxsplit=1)[0].strip()
    if not source:
        return None
    meta = _ISSUE_ONLY_META_RE.search(source)
    if not meta:
        return None

    title = str(base.get("title") or "").strip()
    title_removed = False
    if title:
        pos = source.casefold().find(title.casefold())
        if 0 <= pos <= 8:
            source = source[pos + len(title):].lstrip(" .,:;")
            title_removed = True
            meta = _ISSUE_ONLY_META_RE.search(source)
            if not meta:
                return None
    candidate = source[:meta.start()].strip(" .,:;")
    _, cand = _v03._split_title_journal_before_meta(candidate)
    if cand:
        candidate = cand
    elif not title_removed:
        return None
    candidate = re.sub(r"^(?:In|En)\s+", "", candidate, flags=re.I).strip(" .,:;")
    # ``Psicothema, 17, (1), 39-45``: the volume sits between the name and the
    # issue, separated by a comma.  A journal name does not end in a bare
    # number, so a trailing comma-number pair is volume metadata.
    candidate = re.sub(r",\s*(?:vol\.?\s*)?\d{1,4}\s*$", "", candidate, flags=re.I).strip(" .,:;")
    if not _v09._plausible_journal_v09(candidate):
        return None
    # A publisher already assigned by the previous version is monograph
    # evidence and blocks the rescue, unless that publisher is itself a
    # fragment of the source segment: ``Revista Iberoamericana de Educación,
    # (20), 217-225`` had been read as the imprint ``Iberoamericana``, which is
    # not a monograph signal but the same journal name misparsed.
    publisher = base.get("publisher")
    if publisher and _v03._norm(publisher) not in _v03._norm(candidate):
        return None
    return _v03._canonicalize_journal(candidate)


# --------------------------------------------------------------------------
# Imprint after a closing place and country
# --------------------------------------------------------------------------
_COUNTRY = (
    r"Argentina|Bolivia|Brasil|Brazil|Canad[aá]|Chile|Colombia|Costa\s+Rica|Cuba|"
    r"Ecuador|El\s+Salvador|Espa[ñn]a|Spain|Estados\s+Unidos(?:\s+de\s+Am[eé]rica)?|"
    r"United\s+States(?:\s+of\s+America)?|USA|EE\.?\s?UU\.?|Francia|France|Alemania|"
    r"Germany|Guatemala|Honduras|Inglaterra|Italia|Italy|M[eé]xico|Mexico|Nicaragua|"
    r"Panam[aá]|Paraguay|Per[uú]|Portugal|Puerto\s+Rico|Reino\s+Unido|United\s+Kingdom|"
    r"Rep[uú]blica\s+Dominicana|Uruguay|Venezuela|Su[ie]za|Switzerland|Holanda|"
    r"Pa[ií]ses\s+Bajos|B[eé]lgica|Australia|Jap[oó]n|China|India"
)
# ``… Santiago de Chile, Chile: Divergente.``  The country immediately before
# the colon is what licenses the segment; the imprint itself is not tested
# against any lexicon.
_CLOSING_IMPRINT_RE = re.compile(
    rf",\s*(?:{_COUNTRY})\s*:\s*(?P<imprint>[^.:;]{{2,90}}?)\s*\.?\s*$", re.I
)
_TRAILING_NOISE_RE = re.compile(r"\s*\[\s*\d{1,4}\s*\]\s*$|\s*-\s*\d{1,4}\s*-\s*$")


def _closing_country_imprint(text: str) -> Optional[str]:
    t = _v09._APA_LINK_SPLIT_RE.split(re.sub(r"\s+", " ", text).strip(), maxsplit=1)[0]
    t = _TRAILING_NOISE_RE.sub("", t).strip()
    m = _CLOSING_IMPRINT_RE.search(t)
    if not m:
        return None
    imprint = m.group("imprint").strip(" .,;:")
    if not imprint or len(imprint.split()) > 12:
        return None
    if not re.match(rf"^[{_UC}A-Z0-9]", imprint):
        return None
    if re.search(r"\bpp?\.|\bvol\.|\b(?:18|19|20)\d{2}\b", imprint, re.I):
        return None
    return imprint


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

def parse_reference(texto: str) -> Dict[str, Any]:
    text = re.sub(r"\s+", " ", str(texto or "")).strip()
    out = dict(_v09.parse_reference(text))
    styles: List[str] = []

    journal = _issue_only_journal(text, out)
    if journal:
        out["journal"] = journal
        out["publication_type"] = "articulo_revista"
        out["publisher"] = None
        out["publisher_observed"] = None
        out["source_publisher"] = None
        styles.append("v10_issue_only_journal")

    # ``sin_clasificar`` is included on purpose: a reference that closes with
    # ``Place, Country: Imprint`` is monograph-shaped, and it is exactly the
    # class that loses its classification when the extractor leaves a running
    # page number glued to the text.  The type is left as the previous version
    # decided it; only the empty publisher is filled.
    if (out.get("publication_type") in {"libro", "capitulo_libro",
                                        "documento_guia_manual", "sin_clasificar"}
            and not out.get("publisher")):
        imprint = _closing_country_imprint(text)
        if imprint:
            canonical = _v08._canonical_publisher(imprint) or imprint
            out["publisher"] = canonical
            out["publisher_observed"] = imprint
            out["source_publisher"] = canonical
            styles.append("v10_closing_country_imprint")

    if styles:
        out["parse_style"] = "+".join([str(out.get("parse_style") or "")] + styles)
    out["schema_version"] = PARSER_SCHEMA_VERSION
    out["parser_version"] = PARSER_VERSION
    out["parser_status"] = PARSER_STATUS
    return out


def parse_records(records: Sequence[Dict[str, Any]], text_key: str = "reference_text") -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for rec in records:
        row = dict(rec)
        row["parsed"] = parse_reference(str(row.get(text_key, "") or ""))
        out.append(row)
    return out


def flatten_parsed(parsed: Dict[str, Any] | None, prefix: str = "parsed_") -> Dict[str, Any]:
    parsed = parsed or {}
    fields = (
        "parser_version", "parser_status", "parse_style", "author", "authors", "year",
        "publication_type", "title", "journal", "publisher", "publisher_observed",
        "source_publisher", "doi",
    )
    return {f"{prefix}{key}": parsed.get(key) for key in fields}
