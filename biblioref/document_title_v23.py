from __future__ import annotations

"""Title-reading v2.3: reject front-matter people from title ranking.

This revision keeps the validated v2.1 geometry/scoring and the v2.2
administrative-role barriers. It adds one conservative rule: a title candidate
that is effectively the same personal name as an already known author,
director/codirector, or a person explicitly attached to a front-matter role is
removed before ranking. Real title phrases that merely mention a person's name
are not rejected.
"""
from pathlib import Path
from typing import Iterable
import math
import re
import unicodedata

# Importing v2.2 installs its expanded tribunal/jury/committee role vocabulary
# into the base detector. We then reuse the same candidate geometry and scores.
from . import document_title_v22 as _v22  # noqa: F401
from . import document_title as _base

TITLE_READING_REVISION = "document-title-v2.3"

_ROLE_PREFIX_RE = re.compile(
    r"^(?:"
    r"autor(?:a|es)?|author|presentad[oa]\s+por|presented\s+by|tesista|candidate|"
    r"director(?:a)?(?:\s+de\s+tesis)?|co-?director(?:a)?(?:\s+de\s+tesis)?|"
    r"supervisor|co-?supervisor|advisor|adviser|co-?advisor|co-?adviser|"
    r"orientador(?:a)?|co-?orientador(?:a)?|tutor(?:a)?|co-?tutor(?:a)?|"
    r"tribunal(?:\s+(?:evaluador|examinador|de\s+tesis))?|"
    r"jurado(?:\s+(?:evaluador|de\s+tesis))?|miembros\s+del\s+(?:tribunal|jurado)|"
    r"comit[eé](?:\s+(?:evaluador|de\s+tesis))?|comisi[oó]n\s+evaluadora|"
    r"evaluation\s+committee|examining\s+committee|examination\s+committee|"
    r"thesis\s+committee|doctoral\s+committee|jury|examiners?|examiner|review\s+committee|"
    r"banca(?:\s+(?:examinadora|de\s+defesa))?|membros\s+da\s+banca|"
    r"comiss[aã]o\s+julgadora"
    r")\b\s*[:.\-–—]?\s*",
    re.I,
)
_PERSON_PREFIX_RE = re.compile(
    r"^(?:(?:lic|licda|mg|mgtr|msc|m\.?sc|dr|dra|prof|profesor|profesora|mr|mrs|ms|ph\.?d)\.?\s+)+",
    re.I,
)
_PARTICLES = {"de", "del", "la", "las", "los", "y", "e", "da", "do", "dos", "van", "von"}
_ROLE_WORDS = {
    "autor", "autora", "author", "tesista", "candidate", "director", "directora",
    "codirector", "codirectora", "supervisor", "advisor", "adviser", "orientador",
    "orientadora", "tutor", "tutora", "tribunal", "jurado", "evaluador", "evaluadora",
    "examiner", "jury", "committee",
}


def _fold(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _name_tokens(value: str) -> tuple[str, ...]:
    text = _PERSON_PREFIX_RE.sub("", _base.clean(value))
    tokens = [
        _fold(token).strip(".'’-")
        for token in _base.words(text)
    ]
    return tuple(token for token in tokens if token and token not in _PARTICLES and token not in _ROLE_WORDS)


def title_conflicts_with_people(title: str, people: Iterable[str] = ()) -> bool:
    """Return True only when *title* is essentially the same person name.

    Matching is deliberately stricter than substring matching: order may differ
    ("Pérez, Juan" vs "Juan Pérez"), honorifics/role labels may differ, but the
    significant name-token set must be the same. Thus a legitimate title such
    as "La recepción de Freud en Argentina" is not suppressed merely because a
    known person is named Freud.
    """
    candidate = _name_tokens(title)
    if not (2 <= len(candidate) <= 8):
        return False
    cset = set(candidate)
    for person in people:
        ptokens = _name_tokens(person)
        if not (2 <= len(ptokens) <= 8):
            continue
        if cset == set(ptokens) and abs(len(candidate) - len(ptokens)) <= 1:
            return True
    return False


def _inline_role_person(text: str) -> str:
    raw = _base.clean(text)
    match = _ROLE_PREFIX_RE.match(raw)
    if not match:
        return ""
    value = raw[match.end():].strip(" .:;,-–—")
    return value if _base.likely_person_name(value) else ""


def _role_linked_people(pdf, max_pages: int = 6) -> list[str]:
    """Collect names explicitly linked to author/advisor/jury role labels.

    These names are used only as negative evidence for title ranking. They are
    not persisted as metadata, so this does not broaden the metadata schema.
    """
    found: list[str] = []
    for pno in range(min(max_pages, len(pdf))):
        lines = _base.extract_lines(pdf[pno], pno)
        for i, line in enumerate(lines):
            inline = _inline_role_person(line.text)
            if inline:
                found.append(inline)
                continue
            if not _ROLE_PREFIX_RE.match(_base.clean(line.text)):
                continue
            anchor = line
            for nxt in lines[i + 1:i + 4]:
                text = _base.clean(nxt.text)
                if not text:
                    continue
                if _ROLE_PREFIX_RE.match(text) or _base.has_term(text, _base.INST_TERMS) or _base.has_term(text, _base.DEGREE_TERMS):
                    break
                gap = nxt.y0 - anchor.y1
                if gap > max(42.0, 3.0 * max(anchor.size, nxt.size, 1.0)):
                    break
                if _base.likely_person_name(text):
                    found.append(text)
                    break
    # Preserve order for diagnostics/tests while removing normalized duplicates.
    out: list[str] = []
    seen: set[tuple[str, ...]] = set()
    for value in found:
        key = _name_tokens(value)
        if key and key not in seen:
            seen.add(key)
            out.append(value)
    return out


def detect_thesis_title(
    path: Path,
    filename: str,
    *,
    excluded_people: Iterable[str] = (),
) -> tuple[str, str]:
    """Detect a thesis title while excluding known front-matter personal names."""
    path = Path(path)
    filename = str(filename)
    fallback = _base.filename_as_title(filename)
    if _base.fitz is None:
        return fallback, "filename"
    try:
        with _base.fitz.open(path) as pdf:
            people = [str(x) for x in excluded_people if str(x or "").strip()]
            people.extend(_role_linked_people(pdf))

            ranked = [
                candidate for candidate in _base.layout_candidates(pdf)
                if not title_conflicts_with_people(candidate.text, people)
            ]

            meta = _base.clean((pdf.metadata or {}).get("title") or "")
            ms = _base.metadata_score(meta, fallback)
            if math.isfinite(ms) and not title_conflicts_with_people(meta, people):
                overlap = max((_base.similarity(meta, c.text) for c in ranked), default=0)
                if overlap >= 0.72:
                    ms += 20
                page_cover = 0.0
                for pno in range(min(3, len(pdf))):
                    lines = _base.extract_lines(pdf[pno], pno)
                    if _base.page_role(lines) == "repository-coversheet":
                        continue
                    evidence = " ".join(x.text for x in lines if x.yr <= 0.68)
                    page_cover = max(page_cover, _base._token_coverage(meta, evidence))
                if page_cover >= 0.90:
                    ms += 34
                elif page_cover >= 0.75:
                    ms += 22
                ranked.append(_base.Candidate(meta, ms, "pdf_metadata", -1))

            if ranked:
                ranked.sort(key=lambda c: (c.score, len(c.text)), reverse=True)
                best = ranked[0]
                if best.score >= 24 and _base.plausible(best.text):
                    return best.text, best.source
    except Exception:
        pass
    return fallback, "filename"


__all__ = [
    "TITLE_READING_REVISION",
    "detect_thesis_title",
    "title_conflicts_with_people",
]
