# -*- coding: utf-8 -*-
"""Small deterministic normalizers used by metadata resolver backends."""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable, Optional, Tuple

_DOI_PREFIX_RE = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi\s*:\s*)", re.I)
_DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.I)
_YEAR_RE = re.compile(r"(?<!\d)((?:18|19|20)\d{2})(?!\d)")


def clean_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return re.sub(r"\s+", " ", text).strip()


# --- query hygiene -------------------------------------------------------
#
# Text extracted from a PDF carries artefacts that a human reader sees through
# and a search API does not: soft hyphens, typographic dashes, curly quotes,
# zero-width characters and words split across a line break. They do not belong
# to the reference, they belong to the extraction, so they are repaired on the
# way *out* to a backend. Parser output itself is never rewritten.

_ZERO_WIDTH_RE = re.compile("[­​‌‍⁠﻿]")
_DASH_RE = re.compile("[‐‑‒–—―−]")
_SINGLE_QUOTE_RE = re.compile("[‘’‚‛‹›ʼ´`]")
_DOUBLE_QUOTE_RE = re.compile("[“”„‟«»]")
# A word broken at a line break resumes in lowercase ("differen- tiated"), so
# the hyphen goes away. A hyphenated proper noun broken at the same place
# resumes in uppercase ("Baron- Cohen"), and there the hyphen is part of the
# name: only the stray space goes away. Case is what tells them apart, so this
# pair is deliberately case-sensitive.
_LINEBREAK_HYPHEN_RE = re.compile(r"(?<=[a-záéíóúüñç])-\s+(?=[a-záéíóúüñç])")
_SPLIT_COMPOUND_RE = re.compile(r"(?<=[A-Za-zÀ-ÖØ-öø-ÿ])-\s+(?=[A-ZÁÉÍÓÚÜÑÇ])")
#
# There is deliberately no rule closing up " - ". In this corpus a spaced dash
# is far more often a field separator ("Autor – 2003 – Título – Editorial")
# than a split compound, and gluing those together destroys the token
# boundaries a bibliographic search depends on. Mapping the exotic dash
# codepoints to ASCII is enough: backends tokenise on the hyphen either way.
# Only multi-word markers, never a bare word: "Acceso" alone also appears inside
# titles ("La Mediación y el Acceso a Justicia"), and cutting there destroys the
# reference instead of cleaning it.
_ACCESS_TAIL_RE = re.compile(
    r"\s*[\[(]?\s*(?:recuperado\s+(?:de|a\s+partir\s+de)|disponible\s+en|"
    r"retrieved\s+from|available\s+(?:at|from)|consultad[oa]\s+(?:el|en)|"
    r"fecha\s+de\s+(?:consulta|acceso)|(?:último|ultimo|last)\s+acceso|"
    r"fecha\s+de\s+última\s+consulta)\b.*$",
    re.I | re.S,
)
# A hygiene step may never eat the reference. If a strip would remove most of
# what is there, the marker was almost certainly part of the text itself.
_MIN_KEPT_RATIO = 0.6
_MIN_KEPT_CHARS = 40
_INDEX_NOISE_RE = re.compile(r"\s*\[\s*(?:links?|google\s+scholar|crossref|pubmed|scielo)\s*\]", re.I)


def clean_query_text(value: Any) -> str:
    """Repair PDF extraction artefacts before a reference is sent to a backend.

    This is lossy on purpose and is never written back to the parsed record:
    the text it produces exists only to be searched with.
    """
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = _ZERO_WIDTH_RE.sub("", text)
    text = _DASH_RE.sub("-", text)
    text = _SINGLE_QUOTE_RE.sub("'", text)
    text = _DOUBLE_QUOTE_RE.sub('"', text)
    # "differen- tiated" is one word the extractor split at a line break.
    text = _LINEBREAK_HYPHEN_RE.sub("", text)
    # "Baron- Cohen" is a hyphenated name split at the same place.
    text = _SPLIT_COMPOUND_RE.sub("-", text)
    return re.sub(r"\s+", " ", text).strip()


def strip_reference_noise(value: Any) -> str:
    """Drop access trails and index badges from a reference used as a query.

    ``Recuperado de http://...`` and ``[ Links ]`` are artefacts of where the
    reference was published, not of the work being cited, and they dilute a
    bibliographic search.
    """
    text = clean_query_text(value)
    text = _INDEX_NOISE_RE.sub("", text)

    trimmed = _ACCESS_TAIL_RE.sub("", text)
    if trimmed is not text and len(trimmed) < min(_MIN_KEPT_CHARS, len(text)):
        trimmed = text
    elif text and len(trimmed) / len(text) < _MIN_KEPT_RATIO:
        trimmed = text

    return trimmed.strip(" .;,-")


def normalize_match_text(value: Any) -> str:
    text = clean_text(value).casefold()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_doi(value: Any) -> Optional[str]:
    text = clean_text(value)
    if not text:
        return None
    text = _DOI_PREFIX_RE.sub("", text).strip().rstrip(".,;)")
    match = _DOI_RE.search(text)
    return match.group(0).lower() if match else None


def normalize_year(value: Any) -> Optional[str]:
    match = _YEAR_RE.search(clean_text(value))
    return match.group(1) if match else None


def normalize_authors(value: Any) -> Tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        parts = re.split(r"\s*;\s*|\s+and\s+|\s+y\s+|\s+&\s+", value)
        return tuple(clean_text(x) for x in parts if clean_text(x))
    if isinstance(value, dict):
        value = [value]
    if isinstance(value, Iterable):
        out = []
        for item in value:
            if isinstance(item, dict):
                name = item.get("display_name") or item.get("name") or item.get("literal")
                if not name:
                    family = clean_text(item.get("family") or item.get("family_name"))
                    given = clean_text(item.get("given") or item.get("given_name"))
                    name = ", ".join(x for x in (family, given) if x)
            else:
                name = item
            name = clean_text(name)
            if name:
                out.append(name)
        return tuple(out)
    text = clean_text(value)
    return (text,) if text else ()
