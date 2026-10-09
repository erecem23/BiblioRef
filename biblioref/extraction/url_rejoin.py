# -*- coding: utf-8 -*-
"""0.6.17: rejoin URLs that a line break split inside a reference.

Segmenters join the physical lines of a reference with a space. When a URL
crosses the line, that space stays inside it («…/obligatorias/0
42_ttedm2c2/…», «?sequence=1&isAllo wed=y»). A URL has no spaces, so a space
inside one is removed when what follows it is still URL: it carries a URL
character (/ = & % ? # _ ;), a file extension, or is a hexadecimal run. Another
URL, a date or a word of prose after the URL is never joined.

0.6.19: a query value cut after «=» («download.php?gal_id= 479») and a hyphenated
file slug cut between words («…/actas-de-las primeras-jornadas-del
departamento de psicoanálisis-2.pdf») are joined. The slug is only rebuilt when
lowercase slug words run up to a token with a file extension; the words are
joined with the hyphen the slug already uses.
"""
from __future__ import annotations

import re

_URL_START_RE = re.compile(r"(?:https?://|www\.)\S*", re.I)
_URL_CHAR_RE = re.compile(r"[/=&%?#_;]|\.(?:pdf|html?|php|aspx?|jsp|xml|docx?)\b", re.I)
_HEX_RUN_RE = re.compile(r"^(?=[0-9a-f]*\d)[0-9a-f]{6,}[/?&=.\-]?", re.I)
_DATE_RE = re.compile(r"^\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}\b")
_NEXT_TOKEN_RE = re.compile(r" (\S+)")
_QUERY_VALUE_RE = re.compile(r"^(?=\S*\d)[A-Za-z0-9][\w%.\-]*$")
_SLUG_TAIL_RE = re.compile(r"/[a-z0-9]+(?:-[a-z0-9]+)+$")
_SLUG_WORD_RE = re.compile(r"^[a-z0-9áéíóúñü]+(?:-[a-z0-9áéíóúñü]+)*$")
_SLUG_END_RE = re.compile(r"^[a-z0-9áéíóúñü]+(?:-[a-z0-9áéíóúñü]+)*\.(?:pdf|html?|php|docx?)[.,;]?$")
_SLUG_MAX_WORDS = 4


def _continues_url(url: str, following: str) -> bool:
    if re.match(r"(?:https?:|www\.|doi:)", following, re.I) or _DATE_RE.match(following):
        return False
    if url.endswith((")", "]", ",", ";")):
        return False
    if url.endswith("=") and _QUERY_VALUE_RE.match(following.rstrip(".,;")):
        return True
    # «…/index.html. Buenos Aires»: after a closing period only lowercase URL text continues.
    if url.endswith(".") and not (following[:1].islower() or following[:1].isdigit()):
        return False
    return bool(_URL_CHAR_RE.search(following) or _HEX_RUN_RE.match(following))


def _slug_run(out: str, url: str, end: int) -> list:
    """Spans of the spaces to turn into hyphens, or [] when no file slug continues."""
    if not _SLUG_TAIL_RE.search(url):
        return []
    spaces, position = [], end
    for _ in range(_SLUG_MAX_WORDS):
        following = _NEXT_TOKEN_RE.match(out, position)
        if not following:
            return []
        spaces.append(position)
        token = following.group(1)
        # The word right after the cut must itself be slug-shaped («primeras-jornadas-del»).
        if len(spaces) == 1 and "-" not in token:
            return []
        if _SLUG_END_RE.match(token):
            return spaces
        if not _SLUG_WORD_RE.match(token):
            return []
        position = following.end()
    return []


def rejoin_broken_urls(text: str) -> str:
    out = str(text or "")
    position = 0
    while True:
        match = _URL_START_RE.search(out, position)
        if not match:
            return out
        end = match.end()
        while True:
            following = _NEXT_TOKEN_RE.match(out, end)
            if not following:
                break
            if not _continues_url(out[match.start():end], following.group(1)):
                slug = _slug_run(out, out[match.start():end], end)
                if not slug:
                    break
                for space in slug:
                    out = out[:space] + "-" + out[space + 1:]
                end = re.compile(r"\S+").match(out, slug[-1] + 1).end()
                continue
            out = out[:end] + out[end + 1:]
            end = end + len(following.group(1))
        position = end
