from __future__ import annotations

import re
from typing import Any, Iterable, Sequence

YEAR_RX = re.compile(r"\b(?:18|19|20)\d{2}[a-z]?\b", re.I)
PAREN_YEAR_RX = re.compile(r"\((?:18|19|20)\d{2}[a-z]?\)", re.I)
BARE_YEAR_RX = re.compile(r"[,;]\s*(?:18|19|20)\d{2}[a-z]?\s*[,.:]", re.I)
EDITOR_RX = re.compile(r"\b(?:eds?\.?|editors?|coords?\.?|comp(?:s|iladores?)?\.?)\b", re.I)
AUTHORISH_RX = re.compile(
    r"^(?:[A-ZÁÉÍÓÚÜÑÀ-ÖØ-Þ][A-Za-zÁÉÍÓÚÜÑáéíóúüñÀ-ÿ'’\-]+(?:\s+[A-ZÁÉÍÓÚÜÑÀ-ÖØ-Þ][A-Za-zÁÉÍÓÚÜÑáéíóúüñÀ-ÿ'’\-]+){0,5}"
    r"(?:\s*[,;:]|\s+(?:and|y|&|et\s+al\.?))|[A-ZÁÉÍÓÚÜÑÀ-ÖØ-Þ][A-Za-zÁÉÍÓÚÜÑáéíóúüñÀ-ÿ'’\-]+,\s*[A-Z])",
    re.I,
)
CONTINUATION_WORDS = re.compile(r"^(?:and|y|&|en|in|of|de|del|la|las|los|the|pp?\.|vol\.?|no\.?|n[oº°]\.?|press\b)", re.I)
TERMINAL_RX = re.compile(r"[.)\]\"'’]\s*$")
FOLIO_RX = re.compile(r"[-–—\s]*(?:\d{1,4}|[ivxlcdm]{1,6}|\[\s?\d{1,4}\s?\])[-–—\s]*", re.I)
LIST_MARKER_RX = re.compile(r"^\s*(?:[○●•◦▪▫■□·\-–—*]+|\[\s?\d{1,4}\s?\]|\d{1,4}[.)])\s*[-–—]?\s*(?=\S)")
URL_START_RX = re.compile(r"(?:https?\s*:\s*/|www\.|doi\s*:|10\.\d{4,9}/)", re.I)
URL_END_RX = re.compile(r"(?:https?://|www\.)\S*$", re.I)
OPEN_END_RX = re.compile(r"(?:[,;:/\-–—]|\b(?:and|y|de|del|en|in|of|the))\s*$", re.I)


def _text(item: Any) -> str:
    if hasattr(item, "text"):
        return str(item.text or "").strip()
    if isinstance(item, dict):
        return str(item.get("text") or item.get("reference_text") or "").strip()
    return str(item or "").strip()


def _sequence(items: Any) -> list[str]:
    if items is None:
        return []
    if isinstance(items, (str, bytes)):
        return [_text(items)]
    return [t for t in (_text(x) for x in items) if t]


def _looks_like_author_start(text: str) -> bool:
    t = text.strip()
    if not t or not t[:1].isupper():
        return False
    if PAREN_YEAR_RX.search(t[:220]) or BARE_YEAR_RX.search(t[:220]):
        return bool(AUTHORISH_RX.match(t) or re.match(r"^[A-ZÁÉÍÓÚÜÑ][^.!?]{1,90}[,;]", t))
    return bool(AUTHORISH_RX.match(t))


def evaluate_page_boundary(previous_tail: Any, next_head: Any) -> dict[str, Any]:
    """Classify one physical page boundary without treating the page break as evidence itself.

    Returns split/continue/review plus auditable evidence. This is intentionally
    conservative: it is a review helper, not an automatic re-segmenter.
    """
    prev = _sequence(previous_tail)
    nxt = _sequence(next_head)
    # 0.6.17: a folio («292», «- 24 -») is not the last line of the reference,
    # and a list marker («○», «•», «-», «12.», «[12]») is not part of the first.
    prev_lines = [t for t in prev if not FOLIO_RX.fullmatch(t)]
    next_lines = [LIST_MARKER_RX.sub("", t, count=1) for t in nxt if not FOLIO_RX.fullmatch(t)]
    prev_text = " ".join(prev_lines[-3:]).strip()
    nxt = next_lines or nxt
    head0 = nxt[0].strip() if nxt else ""
    head_join = " ".join(nxt[:3]).strip()

    split_support = 0
    continue_support = 0
    evidence: list[dict[str, Any]] = []

    if head0 and _looks_like_author_start(head0):
        split_support += 2
        evidence.append({"signal": "next_starts_like_author", "direction": "split"})
    if head_join and YEAR_RX.search(head_join[:260]) and _looks_like_author_start(head0):
        split_support += 2
        evidence.append({"signal": "year_found_near_next_start", "direction": "split"})
    if EDITOR_RX.search(head0) and YEAR_RX.search(head_join[:300]):
        split_support += 2
        evidence.append({"signal": "editor_marker_with_deferred_year", "direction": "split"})
    if prev_text and TERMINAL_RX.search(prev_text):
        split_support += 1
        evidence.append({"signal": "previous_tail_looks_closed", "direction": "split"})
    # «…/transhipocratismo/»: the slash closes a URL, it does not leave the line open.
    if prev_text and OPEN_END_RX.search(prev_text) and not URL_END_RX.search(prev_text):
        continue_support += 2
        evidence.append({"signal": "previous_tail_looks_open", "direction": "continue"})
    # 0.6.17: a URL or DOI never opens a reference; at the top of a page it is
    # the tail of the one above.
    if head0 and URL_START_RX.match(head0):
        continue_support += 3
        evidence.append({"signal": "next_starts_with_url", "direction": "continue"})
    if head0 and (head0[:1].islower() or CONTINUATION_WORDS.match(head0)):
        continue_support += 2
        evidence.append({"signal": "next_starts_like_continuation", "direction": "continue"})
    if head0 and not _looks_like_author_start(head0) and not YEAR_RX.search(head_join[:260]):
        continue_support += 1
        evidence.append({"signal": "no_new_reference_signature_at_next_start", "direction": "continue"})

    if split_support >= continue_support + 2 and split_support >= 3:
        verdict = "split"
    elif continue_support >= split_support + 2 and continue_support >= 2:
        verdict = "continue"
    else:
        verdict = "review"
    return {
        "verdict": verdict,
        "split_support": split_support,
        "continue_support": continue_support,
        "evidence": evidence,
        "previous_tail": prev[-3:],
        "next_head": nxt[:3],
    }
