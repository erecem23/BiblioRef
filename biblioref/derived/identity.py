# -*- coding: utf-8 -*-
"""Work identity for corpus-level analysis.

Counting works instead of strings needs a key that says when two references
describe the same thing. Without external identifiers this can only be a
deterministic approximation, so the rules are explicit, the key records which
rule produced it, and every reference that cannot get one is counted as an
exclusion rather than silently dropped.

Two keys are produced deliberately:

``work_key``        includes the year. This is the conservative key: it never
                    merges a 1905 edition with its 1976 translation, at the
                    cost of splitting re-editions of the same work.
``work_key_loose``  drops the year. Measured over this corpus it collapses a
                    further 1,4 % of keys — concentrated in books (4,0 %),
                    where re-editions are the norm — which is what makes the
                    difference between the two a reportable number rather than
                    a hidden assumption.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional, Tuple

from biblioref.resolver.normalize import clean_text, normalize_match_text

IDENTITY_VERSION = "work-identity-v0.1"

TITLE_WORDS = 8
MIN_TITLE_KEY_CHARS = 10


def surname(authors: Any) -> str:
    """First author's family name, normalized for matching.

    Only the first author is used: reference styles disagree about how many
    authors to list and in what order the given names go, but they agree on
    who comes first.
    """
    text = clean_text(authors)
    if not text:
        return ""
    head = text.split(";")[0]
    if "," in head:
        head = head.split(",")[0]
    else:
        parts = head.split()
        head = parts[-1] if parts else ""
    return normalize_match_text(head)


def title_key(title: Any, words: int = TITLE_WORDS) -> str:
    """Leading content words of a title.

    Short words are dropped because they are where reference styles differ
    most (articles, prepositions, ampersands), and the tail is dropped because
    subtitles are quoted inconsistently.
    """
    normalized = normalize_match_text(title)
    return " ".join([w for w in normalized.split() if len(w) > 2][:words])


def _looks_like_a_title(title: Any, author: Any) -> bool:
    """Reject the parse failure where the title repeats the author block.

    This is a known parser outcome (about 1,1 % of the corpus) and it would
    otherwise fuse every failed parse by the same author into one fake work.
    """
    normalized = normalize_match_text(title)
    if not normalized:
        return False
    return normalized != normalize_match_text(author)


def work_keys(row: Mapping[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """Return ``(work_key, work_key_loose)`` for one reference row.

    ``None`` means the reference carries too little evidence to be identified
    and must be excluded from work-level counts.
    """
    doi = clean_text(row.get("doi"))
    if doi:
        key = f"doi:{doi.lower()}"
        return key, key

    author = row.get("authors") or row.get("author")
    family = surname(author)
    year = clean_text(row.get("year"))
    stem = title_key(row.get("title"))

    if not family or len(stem) < MIN_TITLE_KEY_CHARS:
        return None, None
    if not _looks_like_a_title(row.get("title"), author):
        return None, None

    loose = f"sa:{family}|{stem}"
    if not year:
        return None, loose
    return f"sya:{family}|{year}|{stem}", loose
