"""General multiline-continuity guards introduced from the v0.8.3 external pilot."""

from __future__ import annotations

import re
from typing import Dict, Sequence

from biblioref.adaptive.order_profile import PARTICLE_AUTHOR_RX
from biblioref.detection.signals import bare_author_year, parenthetical_author_year
from biblioref.legacy.engine import NUMERIC_MARKER_RX, LayoutLine, YEAR_RX, SIN_FECHA_RX
from biblioref.grammar.dates import UNDATED_RX, undated_author_start

DOI_OR_URL_RX = re.compile(r"(?:doi\s*:|https?://|www\.|10\.\d{4,9}/)", re.I)
AUTHOR_LIST_END_RX = re.compile(r"(?:,|\s)(?:y|e|and|&|et)\s*$", re.I)
MANY_AUTHOR_TOKENS_RX = re.compile(r"(?:,[^,]{0,35}){3,}")
AUTHOR_INITIAL_RX = re.compile(r",\s*[A-ZÁÉÍÓÚÑ](?:\.|,)")
SOURCE_CONTINUATION_RX = re.compile(
    r"^[A-ZÁÉÍÓÚÀÂÊÔÃÕÇÜÑ][A-Za-zÁÉÍÓÚÀÂÊÔÃÕÇÜÑáéíóúàâêôãõçüñ&:'’\- ]{1,90},\s*"
    r"\d{1,4}(?:\s*\(\s*\d{1,3}\s*\))?\s*,\s*(?:[A-Za-z]?\d|e\d)",
    re.I,
)
ABNT_SOURCE_CONTINUATION_RX = re.compile(
    r"^(?:[A-ZÁÉÍÓÚÀÂÊÔÃÕÇÜÑ][A-Za-zÁÉÍÓÚÀÂÊÔÃÕÇÜÑáéíóúàâêôãõçüñ\-]+(?:\s+[A-Za-zÁÉÍÓÚÀÂÊÔÃÕÇÜÑáéíóúàâêôãõçüñ\-]+){0,5}),\s*"
    r"(?:[A-ZÁÉÍÓÚÀÂÊÔÃÕÇÜÑ]{2,}|[A-Z][a-z]+),?.{0,90}\b(?:v\.|n\.|p\.|Universidade|University|Editora|Editorial)\b",
    re.I,
)
PAGE_DOI_CONTINUATION_RX = re.compile(r"^\s*\d{2,4}\s*[.,;:]?\s*(?:doi\s*:|https?://|10\.\d{4,9}/)", re.I)
JOURNAL_YEAR_VOLUME_CONTINUATION_RX = re.compile(
    r"^[A-ZÁÉÍÓÚÀÂÊÔÃÕÇÜÑ][^,]{2,100},\s*(?:18|19|20)\d{2}\s*;\s*\d{1,4}(?:\(\d+\))?\s*:\s*[A-Za-z]?\d",
    re.I,
)
SOURCE_VOLUME_PAGE_RX = re.compile(r"(?:\bv\.\s*\d|\bn\.\s*\d|\bp\.\s*\d|\bpp?\.\s*\d|\bvol\.?\s*\d)", re.I)
AUTHOR_INITIAL_AFTER_COMMA_RX = re.compile(r"^[^,]{1,70},\s*[A-ZÁÉÍÓÚÑ](?:\.|,)")
INSTITUTIONAL_AUTHOR_DATE_RX = re.compile(
    r"^(?P<name>[A-ZÁÉÍÓÚÀÂÊÔÃÕÇÜÑ][^.!?]{1,150}?)\.\s*\((?P<date>(?:18|19|20)\d{2}[a-z]?(?:\s*[-–—]\s*(?:18|19|20)?\d{2})?)\)",
)
INSTITUTIONAL_AUTHOR_NO_DOT_RX = re.compile(
    r"^(?P<name>[A-ZÁÉÍÓÚÀÂÊÔÃÕÇÜÑ][^.!?]{1,150}?)\s*\((?P<date>(?:18|19|20)\d{2}[a-z]?(?:\s*[-–—]\s*(?:18|19|20)?\d{2})?)\)",
)

INSTITUTIONAL_LATE_DATE_PREFIX_RX = re.compile(r"^(?P<name>[^.!?]{3,150})\.\s*(?P<body>.+)$")
STANDARD_DOCUMENT_RX = re.compile(r"^(?:(?:ABNT|ANSI|BSI|DIN|ISO|IEC|ASTM)\s+)?(?:NBR|ISO|IEC|ASTM|DIN|BS|EN)\s*[A-Z0-9][A-Z0-9.\-/:]*\b")
INSTITUTION_KEYWORD_RX = re.compile(
    r"\b(?:agencia|agency|association|asociaci[oó]n|universidad|university|institut[eo]|institute|"
    r"organization|organisation|organizaci[oó]n|sociedad|society|council|consejo|ministerio|ministry|"
    r"departamento|department|academia|academy|administration|administraci[oó]n|estado|state)\b",
    re.I,
)

SOURCE_NAME_STOP_RX = re.compile(
    r"\b(?:journal|revista|review|proceedings|transactions|letters|quarterly|magazine)\b", re.I
)
PROPER_ORG_TOKEN_RX = re.compile(r"^(?:[A-ZÁÉÍÓÚÀÂÊÔÃÕÇÜÑ][\w'’&/+-]*|[A-Z]{2,})$")
CONFERENCE_CONTINUATION_RX = re.compile(
    r"^[A-ZÁÉÍÓÚÀÂÊÔÃÕÇÜÑ][A-ZÁÉÍÓÚÀÂÊÔÃÕÇÜÑ0-9 &'’:/\-]{8,},\s*\d{1,3},\s*(?:18|19|20)\d{2}",
)
PUBLISHER_YEAR_CONTINUATION_RX = re.compile(
    r"^[A-ZÁÉÍÓÚÀÂÊÔÃÕÇÜÑ][A-Za-zÁÉÍÓÚÀÂÊÔÃÕÇÜÑáéíóúàâêôãõçüñ'’&.\- ]{1,60},\s*(?:18|19|20)\d{2}[a-z]?\.?$"
)
WEB_ACCESS_RX = re.compile(r"(?:https?://|www\.|\baccessed\b|\bacesso em\b|\bconsultado\b)", re.I)
INSTITUTION_COLON_RX = re.compile(r"^(?P<name>[A-ZÁÉÍÓÚÀÂÊÔÃÕÇÜÑ][^:]{1,80}):\s*.+")
DOT_INITIAL_AUTHOR_DATE_RX = re.compile(
    r"^[A-ZÁÉÍÓÚÀÂÊÔÃÕÇÜÑ][A-Za-zÁÉÍÓÚÀÂÊÔÃÕÇÜÑáéíóúàâêôãõçüñ'’\-]{1,70}\.\s*"
    r"(?:[A-ZÁÉÍÓÚÑ]\.\s*){1,4}\((?:18|19|20)\d{2}[a-z]?\)",
)
OPEN_QUOTE_START_RX = re.compile(r'^[“"‘\']')
SOURCE_IN_RX = re.compile(r"\b(?:En|In|Em)\s*:\s*", re.I)
THESIS_CONTINUATION_RX = re.compile(r"\b(?:ph\.?d\.?\s+thesis|doctoral\s+thesis|dissertation|tesis\s+doctoral|tese\s+de\s+doutorado)\b", re.I)
SERIES_END_RX = re.compile(r"\b(?:colecci[oó]n|collection|series|serie|biblioteca)\s*$", re.I)
LOWER_SOURCE_RX = re.compile(r"^[a-záéíóúàâêôãõçüñ].*\b(?i:universidad|university|facultad|faculty|pp?\.|n[º°o]\.?|vol\.?)\b.*(?:18|19|20)\d{2}")
LOCATION_SPLIT_RX = re.compile(r"^[A-ZÁÉÍÓÚÀÂÊÔÃÕÇÜÑ][A-Za-zÁÉÍÓÚÀÂÊÔÃÕÇÜÑáéíóúàâêôãõçüñ'’\-]{1,30},\s*[^,]{2,90},\s*(?:18|19|20)\d{2}[a-z]?\.?$")
PUBLISHERISH_RX = re.compile(r"\b(?:press|editorial|editora|ediciones|edici[oó]n|university|universidad|colecci[oó]n|collection|series|biblioteca|estudio|institution|instituci[oó]n|association|asociaci[oó]n)\b", re.I)

# v0.8.7 development: author/title records whose bibliographic date occurs on
# a later physical line. These describe transferable person/institution
# morphologies rather than citation-style or repository names.
PERSON_LEAD_STOP_RX = re.compile(
    r"^(?:academic|press|publishers?|publishing|thesis|letter|whitepaper|article|report|journal|revista|"
    r"proceedings|conference|congress|symposium|volume|vol\.?|issue|school|faculty|department|university|universidad)$",
    re.I,
)
GIVEN_OR_INITIAL_CLAUSE_RX = re.compile(
    r"^(?:"
    r"(?:[A-ZÁÉÍÓÚÑ]\.\s*){1,5}"
    r"|[A-ZÁÉÍÓÚÀÂÊÔÃÕÇÜÑ][A-Za-zÁÉÍÓÚÀÂÊÔÃÕÇÜÑáéíóúàâêôãõçüñ'’\-]+(?:\s+[A-ZÁÉÍÓÚÑ]\.){0,3}"
    r"|(?:[A-ZÁÉÍÓÚÑ]\.\s*){1,3}[A-ZÁÉÍÓÚÀÂÊÔÃÕÇÜÑ][A-Za-zÁÉÍÓÚÀÂÊÔÃÕÇÜÑáéíóúàâêôãõçüñ'’\-]+"
    r")(?:\s*\((?:ed|eds|editor|editors|trans)\.?\))?$",
    re.I,
)
INITIAL_FIRST_PERSON_RX = re.compile(
    r"^(?:[A-ZÁÉÍÓÚÑ]\.\s*){1,5}[A-ZÁÉÍÓÚÀÂÊÔÃÕÇÜÑ][\w'’\-]{1,60}"
    r"(?:\s+(?:and|&)\s+(?:[A-ZÁÉÍÓÚÑ]\.\s*){1,5}[A-ZÁÉÍÓÚÀÂÊÔÃÕÇÜÑ][\w'’\-]{1,60})?\s*,",
    re.UNICODE,
)
INSTITUTION_TITLE_LEAD_RX = re.compile(
    r"\b(?:association|asociaci[oó]n|university|universidad|universidade|centre|center|agency|security|"
    r"institute|institution|committee|commission|council|government|administration|ministry|department|"
    r"society|academy|organization|organisation|foundation|alumni|alumini)\b",
    re.I,
)
EDITOR_TAIL_RX = re.compile(
    r"^[A-ZÁÉÍÓÚÀÂÊÔÃÕÇÜÑ][A-Za-zÁÉÍÓÚÀÂÊÔÃÕÇÜÑáéíóúàâêôãõçüñ'’\-]{1,60}\s*\((?:ed|eds)\.?\)\s*,",
    re.I,
)
SOURCE_TAIL_LEAD_RX = re.compile(
    r"^(?:academic|press|publishers?|publishing|thesis|dissertation|letter|whitepaper|article|report|"
    r"proceedings|volume|vol\.?|issue|school|faculty|department)\b",
    re.I,
)
SOURCE_ABBREVIATION_RX = re.compile(
    r"\b(?:Phys\.?\s*Rev\.?|Appl\.?\s*Phys\.?\s*Rev\.?|Journal|Revista|Review|Spectrum|Proceedings|Press|Publishers?)\b",
    re.I,
)


# v0.8.6 development: open-set grammar for author/title starts and source tails.
# These expressions deliberately describe bibliographic *forms*, not repositories.
PERSON_SURNAME = r"[A-ZÁÉÍÓÚÀÂÊÔÃÕÇÜÑ][A-Za-zÁÉÍÓÚÀÂÊÔÃÕÇÜÑáéíóúàâêôãõçüñ'’\-]{1,60}"
PERSON_NAME_WORD = r"[A-ZÁÉÍÓÚÀÂÊÔÃÕÇÜÑ][A-Za-zÁÉÍÓÚÀÂÊÔÃÕÇÜÑáéíóúàâêôãõçüñ'’\-]+"
PERSON_INITIAL_TOKEN = r"[A-ZÁÉÍÓÚÑ]\."
AUTHOR_TITLE_START_RX = re.compile(
    rf"^(?:{PERSON_SURNAME}(?:\s+{PERSON_SURNAME}){{0,2}}),\s*"
    rf"(?:(?:{PERSON_INITIAL_TOKEN}|{PERSON_NAME_WORD})\s+){{0,4}}"
    rf"(?:{PERSON_NAME_WORD}|[A-ZÁÉÍÓÚÑ])"
    rf"(?:,\s*(?:and|&|y|e)\s+(?:(?:{PERSON_INITIAL_TOKEN}|{PERSON_NAME_WORD})\s+){{0,4}}(?:{PERSON_NAME_WORD}|[A-ZÁÉÍÓÚÑ]))?"
    rf"\.\s+(?=[‘’“\"']?[A-ZÁÉÍÓÚÀÂÊÔÃÕÇÜÑ])"
)
COMPACT_PERSON_AUTHOR_YEAR_RX = re.compile(
    rf"^{PERSON_SURNAME}(?:\s+{PERSON_SURNAME}){{0,2}}\s+[A-ZÁÉÍÓÚÑ]{{1,5}}\.?\s+(?:18|19|20)\d{{2}}[a-z]?\b"
)
AUTHOR_FRAGMENT_RX = re.compile(
    rf"\b{PERSON_SURNAME}(?:,\s*|\s+)[A-ZÁÉÍÓÚÑ](?:\.[A-ZÁÉÍÓÚÑ])?\."
)
JOURNAL_VOLUME_PAGES_LINK_RX = re.compile(
    r"^[A-ZÁÉÍÓÚÀÂÊÔÃÕÇÜÑ][A-Za-zÁÉÍÓÚÀÂÊÔÃÕÇÜÑáéíóúàâêôãõçüñ&:'’\- ]{1,120}\s+"
    r"\d{1,4}\s*:\s*\d{1,6}\s*[-–—]\s*\d{1,6}\.?\s+.*(?:https?://|www\.|\bdoi\b|10\.\d{4,9}/)",
    re.I,
)
PUBLISHER_WORD_YEAR_RX = re.compile(
    r"^(?:(?:[A-Z][A-Za-z&.'’\-]*\s+){0,3})?(?:Press|Publishers?|Publishing|Editorial|Editora|Ediciones)\s*,\s*(?:18|19|20)\d{2}[a-z]?\.?$",
    re.I,
)

VOLUME_PAGES_IDENTIFIER_RX = re.compile(
    r"^\d{1,4}\s*,\s*\d{1,6}\s*[-–—]\s*\d{1,6}\s*\((?:18|19|20)\d{2}\)\.?\s*.*(?:https?://|www\.|\bdoi\b|10\.\d{4,9}/)",
    re.I,
)
PUNCTUATION_INHERITED_DATE_RX = re.compile(
    r"^\s*[.]{1,2}\s*\(\s*(?:18|19|20)\d{2}[a-z]?\s*\)"
)
ET_AL_AUTHOR_TITLE_RX = re.compile(
    rf"^(?:{PERSON_SURNAME}(?:\s+{PERSON_SURNAME}){{0,2}}),\s*(?:[A-ZÁÉÍÓÚÑ]\.\s*){{1,4}}et\s+al\.\s+(?=[‘’“\"']?[A-ZÁÉÍÓÚÀÂÊÔÃÕÇÜÑ])",
    re.I,
)

# v0.8.5-n: source/publisher tail fragments that carry a link are continuations,
# not standalone web references.  This intentionally targets *tails* (e.g.
# ``& Sons. DOI``) and requires the previous physical line to be incomplete.
SOURCE_LINK_TAIL_RX = re.compile(
    r"^(?:&|and|y|e)\s+(?:sons?|co(?:mpany)?|publishers?|publishing|press)\b", re.I
)

# Access/retrieval metadata belongs to the preceding bibliographic record in many
# web-reference styles. Keep this concept separate from ``web_resource_start`` so
# that a line such as ``Retrieved 23rd July 2023 from https://...`` cannot be
# promoted as a new web reference merely because it contains a URL.
ACCESS_METADATA_PREFIX_RX = re.compile(
    r"^(?:"
    r"retri(?:e)?ved(?:\s+(?:on\s+)?[^:;,]{0,48})?\s+from\b|"
    r"available\s+(?:at|from)\b|"
    r"accessed(?:\s+on)?\b|"
    r"dispon[ií]vel\s+em\b|"
    r"disponible\s+en\b|"
    r"acesso\s+em\b|"
    r"consultado(?:\s+en)?\b|"
    r"recuperado\s+de\b"
    r")",
    re.I,
)

# Same semantic concept when access metadata is embedded after source/publisher
# material instead of beginning a physical line.  The marker is deliberately
# separable from its surrounding text so we can examine the prefix and avoid
# swallowing legitimate web-reference starts whose author/title comes first.
ACCESS_METADATA_EMBEDDED_RX = re.compile(
    r"(?:\[\s*online\s*\]\s*)?(?:"
    r"retri(?:e)?ved(?:\s+(?:on\s+)?[^:;,]{0,48})?\s+from\b|"
    r"available\s+(?:at|from)\b|"
    r"accessed(?:\s+on)?\b|"
    r"dispon[ií]vel\s+em\b|"
    r"disponible\s+en\b|"
    r"acesso\s+em\b|"
    r"consultado(?:\s+en)?\b|"
    r"recuperado\s+de\b"
    r")",
    re.I,
)
ACCESS_METADATA_ONLINE_PREFIX_RX = re.compile(
    r"^\[\s*online\s*\]\s*(?:available\s+(?:at|from)\b|accessed\b|retrieved\s+from\b)",
    re.I,
)


def particle_author_date(text: str) -> bool:
    raw = text.strip()
    return bool(
        PARTICLE_AUTHOR_RX.match(raw)
        and (YEAR_RX.search(raw[:320]) or SIN_FECHA_RX.search(raw[:320]))
    )



def institutional_author_date(text: str) -> bool:
    """Recognize organization/project authors without requiring a named style.

    Strong forms are ``Institution. (2020)`` and date ranges such as
    ``Grobid. (2008–2023)``. Generic multiword proper names are accepted only
    when the first clause is short and does not look like a journal/source title.
    """
    raw = text.strip()
    match = INSTITUTIONAL_AUTHOR_DATE_RX.match(raw) or INSTITUTIONAL_AUTHOR_NO_DOT_RX.match(raw)
    if not match:
        return False
    name = match.group("name").strip(" .")
    if not name or "," in name or SOURCE_NAME_STOP_RX.search(name):
        return False
    acronym_lead = bool(re.match(r"^[A-Z]{2,}(?:\s+[A-Z][a-z]+)?\b", name))
    if INSTITUTION_KEYWORD_RX.search(name) or acronym_lead:
        return True
    words = [w.strip(".,:;()[]") for w in name.split() if w.strip(".,:;()[]")]
    if not 1 <= len(words) <= 10:
        return False
    proper = sum(bool(PROPER_ORG_TOKEN_RX.match(w)) for w in words)
    function_words = {"de", "del", "la", "las", "los", "of", "the", "and", "y", "e", "do", "da", "dos", "das"}
    content = [w for w in words if w.casefold() not in function_words]
    content_proper = sum(bool(PROPER_ORG_TOKEN_RX.match(w)) for w in content)
    # Function words inside institutional names are neutral rather than negative:
    # ``Congreso de la República de Chile`` is a legitimate bibliographic lead.
    if content and content_proper == len(content) and len(content) >= 2:
        return True
    # Single project/product names (Elsevier, Grobid, Zotero) and multiword
    # proper organizational names (Endeavor South Africa) remain supported.
    return bool((len(words) == 1 and proper == 1) or (len(words) >= 2 and proper >= max(2, len(words) - 1)))

def _plausible_institution_name(name: str) -> bool:
    raw = str(name).strip(" .")
    if not raw or "," in raw or SOURCE_NAME_STOP_RX.search(raw):
        return False
    if INSTITUTION_KEYWORD_RX.search(raw):
        return True
    words = [w.strip(".,:;()[]") for w in raw.split() if w.strip(".,:;()[]")]
    if not 1 <= len(words) <= 16:
        return False
    function_words = {"de", "del", "la", "las", "los", "of", "the", "and", "y", "e", "do", "da", "dos", "das"}
    content = [w for w in words if w.casefold() not in function_words]
    letters = [ch for ch in raw if ch.isalpha()]
    uppercase_ratio = (sum(ch.isupper() for ch in letters) / len(letters)) if letters else 0.0
    if len(content) >= 2 and uppercase_ratio >= 0.80:
        return True
    proper = sum(bool(PROPER_ORG_TOKEN_RX.match(w)) for w in content)
    return bool(content and proper == len(content) and len(content) >= 2)


def institutional_author_late_date(text: str) -> bool:
    """Institutional author whose bibliographic date occurs later in the record.

    Examples include standards bodies and agencies formatted as
    ``Organization. Title... Place, 2020``.  The institutional name itself must
    be organization-like; a journal/source title followed by a year is rejected.
    """
    raw = str(text).strip()
    m = INSTITUTIONAL_LATE_DATE_PREFIX_RX.match(raw)
    if not m or not YEAR_RX.search(m.group("body")):
        return False
    return _plausible_institution_name(m.group("name"))


def standard_document_start(text: str) -> bool:
    """Recognize standard/code records beginning with a formal identifier."""
    raw = str(text).strip()
    return bool(STANDARD_DOCUMENT_RX.match(raw) and YEAR_RX.search(raw))


def dot_initial_author_date(text: str) -> bool:
    """Person-author form extracted as ``Surname. I. (2020)``."""
    return bool(DOT_INITIAL_AUTHOR_DATE_RX.match(str(text).strip()))


def _previous_looks_complete(text: str) -> bool:
    raw = str(text).strip()
    if not raw:
        return False
    if raw.endswith(("-", "–", "—", ",", ":", "/")):
        return False
    if re.search(r"\b(?:and|y|e|et|of|de|del|da|do|dos|das|in|en|el|la|los|las)\s*$", raw, re.I):
        return False
    return bool(raw.endswith((".", ")", "]", ";")))


def implicit_inherited_title_start(index: int, lines: Sequence[LayoutLine]) -> bool:
    """Title-only successor in a bibliography with an inherited/omitted author.

    This is deliberately contextual and open-set. It never rewrites the author;
    it only says that the physical line can plausibly start a new record when
    the prior record looks closed and bibliographic evidence follows shortly.
    """
    if index <= 0 or index >= len(lines):
        return False
    current = lines[index].text.strip()
    previous = lines[index - 1].text.strip()
    if not current or not _previous_looks_complete(previous):
        return False
    if parenthetical_author_year(current) or bare_author_year(current) or institutional_author_date(current) or dot_initial_author_date(current):
        return False
    if source_metadata_continuation(index, lines):
        return False
    # City/publisher/imprint lines are not title-only successors. Short
    # institutional imprints (e.g. ``Smithsonian Institution.``) are especially
    # common wrapped continuations.
    if ":" in current[:60] and not OPEN_QUOTE_START_RX.match(current) and not SOURCE_IN_RX.search(current):
        return False
    first_clause_probe = current.split(".", 1)[0].strip()
    if PUBLISHERISH_RX.search(current) and len(first_clause_probe.split()) <= 2 and not YEAR_RX.search(current):
        return False
    neighborhood = " ".join(l.text.strip() for l in lines[index:min(len(lines), index + 3)])
    has_bib = bool(YEAR_RX.search(neighborhood) or SIN_FECHA_RX.search(neighborhood) or UNDated_safe(neighborhood) or SOURCE_IN_RX.search(neighborhood) or DOI_OR_URL_RX.search(neighborhood))
    if not has_bib:
        return False
    # Quoted titles are the strongest historical omitted-author form.
    if OPEN_QUOTE_START_RX.match(current):
        return True
    # Unquoted title-only records: require a title sentence followed by source or
    # publisher/location evidence, not a comma-led author-like prefix.
    first_clause = current.split(".", 1)[0].strip()
    if "." in current and 2 <= len(first_clause.split()) <= 14 and "," not in first_clause and current[:1].isupper():
        return True
    return False


def UNDated_safe(text: str) -> bool:
    return bool(UNDATED_RX.search(str(text)))


def thesis_metadata_continuation(index: int, lines: Sequence[LayoutLine]) -> bool:
    if index <= 0:
        return False
    current = lines[index].text.strip()
    previous = lines[index - 1].text.strip()
    return bool(THESIS_CONTINUATION_RX.search(current) and previous and not _previous_looks_complete(previous))


def split_location_publisher_continuation(index: int, lines: Sequence[LayoutLine]) -> bool:
    if index <= 0:
        return False
    current = lines[index].text.strip()
    previous = lines[index - 1].text.strip()
    # A cross-record publisher/location tail may leave the previous physical
    # line open (often with a comma).  That must not veto a canonical new
    # person-author + date start on the current line.  Keep this protection
    # local to an explicit strong person/date grammar; generic comma/year
    # fragments such as ``Academic, 2016`` remain eligible continuations.
    if strong_person_author_date(current) and parenthetical_author_year(current):
        return False
    if _previous_looks_complete(previous):
        return False
    if LOCATION_SPLIT_RX.match(current):
        return True
    if previous.endswith(",") and YEAR_RX.search(current) and (PUBLISHERISH_RX.search(current) or len(current.split()) <= 14):
        return True
    if SERIES_END_RX.search(previous) and YEAR_RX.search(current):
        return True
    return False


def quoted_title_continuation(index: int, lines: Sequence[LayoutLine]) -> bool:
    if index <= 0:
        return False
    current = lines[index].text.strip()
    previous = lines[index - 1].text.strip()
    # Previous line opened a quote and the current line closes it before source
    # metadata; this is a wrapped title, not a new inherited title record.
    prev_open = previous.count("“") + previous.count('"') > previous.count("”") + previous.count('"') // 2
    closes = bool(re.match(r'^.{1,80}[”\"]\s*(?:\(|\[|,|\.)', current))
    return bool((prev_open or not _previous_looks_complete(previous)) and closes and SOURCE_IN_RX.search(current))


def lowercase_source_continuation(index: int, lines: Sequence[LayoutLine]) -> bool:
    if index <= 0:
        return False
    current = lines[index].text.strip()
    return bool(current[:1].islower() and YEAR_RX.search(current) and (LOWER_SOURCE_RX.search(current) or PUBLISHERISH_RX.search(current)))


def access_metadata_continuation(index: int, lines: Sequence[LayoutLine]) -> bool:
    """Return True for retrieval/access metadata continuing the previous record.

    The prefix alone is intentionally insufficient.  We also require URL/DOI
    evidence on the same physical line or the immediately following line, and a
    preceding non-heading/content line.  This keeps the rule narrow and avoids
    turning arbitrary prose beginning with ``Retrieved``/``Available`` into a
    forced continuation.
    """
    if index <= 0 or index >= len(lines):
        return False
    current = lines[index].text.strip()
    previous = lines[index - 1].text.strip()
    if not current or not previous or not ACCESS_METADATA_PREFIX_RX.match(current):
        return False
    same_line_link = bool(DOI_OR_URL_RX.search(current))
    next_line_link = False
    if index + 1 < len(lines):
        following = lines[index + 1].text.strip()
        next_line_link = bool(DOI_OR_URL_RX.search(following) or re.match(r"^(?:https?://|www\.|doi\s*:|10\.\d{4,9}/)", following, re.I))
    # Access dates are frequently broken onto a physical line *after* the URL.
    # Look back only two lines to keep this narrow and local.
    prior_link = bool(any(DOI_OR_URL_RX.search(lines[j].text.strip()) for j in range(max(0, index - 2), index)))
    return bool(same_line_link or next_line_link or prior_link)



def reference_with_access_metadata_start(index: int, lines: Sequence[LayoutLine]) -> bool:
    """True when a *new reference* contains access metadata on its first line.

    This is the complement of :func:`embedded_access_metadata_continuation`.
    The access phrase itself is not start evidence.  We require an independent
    author/institution + date (including undated forms) before the access marker,
    plus actual title/body material and a URL/DOI on this line or the next one.
    This keeps lines such as ``982-1003. [Online] Available from:`` as
    continuations while protecting records such as ``Anon. 2004. ... Available
    from:`` and ``CHI Publishers. n.d. ... Available from:``.
    """
    if index < 0 or index >= len(lines):
        return False
    current = lines[index].text.strip()
    if not current:
        return False
    match = ACCESS_METADATA_EMBEDDED_RX.search(current)
    if not match or match.start() == 0:
        return False

    same_line_link = bool(DOI_OR_URL_RX.search(current[match.start():]))
    next_line_link = False
    if index + 1 < len(lines):
        following = lines[index + 1].text.strip()
        next_line_link = bool(DOI_OR_URL_RX.search(following) or re.match(
            r"^(?:<?https?://|www\.|doi\s*:|10\.\d{4,9}/)", following, re.I
        ))
    if not (same_line_link or next_line_link):
        return False

    prefix = current[:match.start()].strip()
    prefix = re.sub(r"\[\s*online\s*\]\s*$", "", prefix, flags=re.I).strip()
    if not prefix:
        return False

    # Existing strong start grammars are authoritative, except that a bare
    # year which is visibly the first half of a title range (1966-1993) must
    # not turn the title into an author-year start.
    first_year = YEAR_RX.search(prefix[:150])
    year_is_range = bool(first_year and re.match(r"\s*[-–—/]\s*(?:18|19|20)\d{2}", prefix[first_year.end():]))
    if (
        parenthetical_author_year(prefix)
        or (bare_author_year(prefix) and not year_is_range)
        or institutional_author_date(prefix)
        or institutional_author_late_date(prefix)
        or undated_author_start(prefix)
        or dot_initial_author_date(prefix)
    ):
        return True

    # A narrower fallback for styles such as ``Anon. 2004. Title`` and
    # ``CHI Publishers. n.d. Title``.  The date must occur early, an actual
    # title/body must follow it, and the lead must look author/institution-like.
    date_match = YEAR_RX.search(prefix[:150]) or UNDATED_RX.search(prefix[:150])
    if not date_match:
        return False
    # A year embedded in a title/range (``Poetry, 1966-1993``) is not a
    # bibliographic date and must not create a protected start.
    after_date = prefix[date_match.end():]
    before_date = prefix[:date_match.start()]
    if re.match(r"\s*[-–—/]\s*(?:18|19|20)\d{2}", after_date) or re.search(r"(?:18|19|20)\d{2}\s*[-–—/]\s*$", before_date):
        return False
    lead_raw = prefix[:date_match.start()].strip(" \t.,;:()[]")
    body = prefix[date_match.end():].strip(" \t.,;:()[]-")
    if not lead_raw or len(lead_raw) > 90 or len(body.split()) < 2:
        return False
    if re.search(r"\b(?:journal|revista|volume|vol\.?|issue|pp?\.?|pages?)\b", lead_raw, re.I):
        return False

    # Person-like ``Surname, I.``
    if re.match(r"^[A-ZÁÉÍÓÚÀÂÊÔÃÕÇÜÑ][^,]{1,60},\s*(?:[A-ZÁÉÍÓÚÑ]\.?\s*){1,4}$", lead_raw):
        return True

    words = re.findall(r"[A-Za-zÁÉÍÓÚÀÂÊÔÃÕÇÜÑáéíóúàâêôãõçüñ0-9&'’.-]+", lead_raw)
    if not 1 <= len(words) <= 8:
        return False
    if len(words) == 1 and words[0].casefold().strip('.') in {"anon", "anonymous", "anónimo", "anonimo"}:
        return True
    org_hint = re.search(
        r"\b(?:publishers?|press|association|society|institute|institution|university|universidad|universidade|"
        r"company|corporation|foundation|committee|commission|council|agency|organisation|organization|department|"
        r"ministry|ministerio|who|unesco)\b",
        lead_raw, re.I,
    )
    acronymish = bool(re.match(r"^[A-Z][A-Z0-9.&-]{1,12}(?:\s+[A-Z][A-Za-z&.-]+){0,3}$", lead_raw))
    return bool(org_hint or acronymish)

def embedded_access_metadata_continuation(index: int, lines: Sequence[LayoutLine]) -> bool:
    """Access/retrieval metadata embedded after bibliographic continuation text.

    Examples include ``982-1003. [Online] Available from: URL`` and
    ``Department of Mathematics, MIT, USA. Retrieved from <URL>``.  A marker
    alone is not enough: a URL/DOI must occur on this line or the next one, and
    any text before the marker must look like continuation material rather than
    a strong new bibliographic start.
    """
    if index <= 0 or index >= len(lines):
        return False
    current = lines[index].text.strip()
    previous = lines[index - 1].text.strip()
    if not current or not previous:
        return False
    if reference_with_access_metadata_start(index, lines):
        return False

    # ``[Online] Available from:`` at line start is semantically the same as the
    # pure-prefix form supported in v0.8.5-i, but the optional Online label kept
    # it outside ACCESS_METADATA_PREFIX_RX.
    online_prefix = ACCESS_METADATA_ONLINE_PREFIX_RX.match(current)
    match = ACCESS_METADATA_EMBEDDED_RX.search(current)
    if not match:
        return False

    marker_pos = match.start()
    prefix = current[:marker_pos].strip(" \t:;,-.[]()")

    same_line_link = bool(DOI_OR_URL_RX.search(current[match.start():]))
    next_line_link = False
    if index + 1 < len(lines):
        following = lines[index + 1].text.strip()
        next_line_link = bool(DOI_OR_URL_RX.search(following) or re.match(
            r"^(?:<?https?://|www\.|doi\s*:|10\.\d{4,9}/|from\b.*(?:https?://|www\.|10\.\d{4,9}/))",
            following, re.I,
        ))
    if not (same_line_link or next_line_link):
        return False

    if online_prefix and marker_pos == 0:
        return True

    # If the material before the retrieval marker is already an unambiguous
    # reference start, this is a legitimate same-line web reference, not a
    # continuation fragment (e.g. ``Breinlinger, T. (n.d.)... Retrieved from``).
    if prefix and (
        parenthetical_author_year(prefix)
        or bare_author_year(prefix)
        or institutional_author_date(prefix)
        or undated_author_start(prefix)
        or dot_initial_author_date(prefix)
    ):
        return False

    # Do not reinterpret a web resource whose URL occurs before an ``Accessed``
    # suffix (``About IBC https://... (Accessed ...)``).  Embedded metadata must
    # introduce, not merely follow, the retrieval link.
    first_link = DOI_OR_URL_RX.search(current)
    if first_link and first_link.start() < marker_pos:
        return False

    # Strong continuation evidence in the prefix or immediately preceding line.
    prefix_continuation = bool(
        not prefix
        or SOURCE_VOLUME_PAGE_RX.search(prefix)
        or PUBLISHERISH_RX.search(prefix)
        or re.search(r"\b(?:department|school|faculty|university|universidad|institute|institution|MIT|USA|UK|press)\b", prefix, re.I)
        or re.search(r"\b\d{1,4}\s*[-–—]\s*\d{1,4}\.?$", prefix)
        or re.search(r"\b\d{1,4}\(\d+\)\s*:\s*\d", prefix)
    )
    previous_incomplete = not _previous_looks_complete(previous)
    return bool(prefix_continuation or previous_incomplete)



def source_with_link_continuation(index: int, lines: Sequence[LayoutLine]) -> bool:
    """Source/publisher tail continuing the previous record while carrying URL/DOI.

    v0.8.5-n keeps this deliberately narrow: the current line must look like a
    publisher/source *tail* (for example ``& Sons.``), it must contain a URL/DOI
    on this line or the next one, and the preceding line must be physically
    incomplete.  Strong author/date starts are never swallowed by this rule.
    Retrieval/access continuations (including the common typo ``Retrived``) are
    handled by :func:`embedded_access_metadata_continuation`.
    """
    if index <= 0 or index >= len(lines):
        return False
    current = lines[index].text.strip()
    previous = lines[index - 1].text.strip()
    if not current or not previous:
        return False
    if (
        parenthetical_author_year(current)
        or bare_author_year(current)
        or institutional_author_date(current)
        or institutional_author_late_date(current)
        or undated_author_start(current)
        or dot_initial_author_date(current)
        or reference_with_access_metadata_start(index, lines)
    ):
        return False
    link_here = bool(DOI_OR_URL_RX.search(current))
    link_next = bool(index + 1 < len(lines) and DOI_OR_URL_RX.search(lines[index + 1].text.strip()))
    if not (link_here or link_next):
        return False
    if _previous_looks_complete(previous):
        return False
    return bool(SOURCE_LINK_TAIL_RX.match(current))

def web_resource_start(index: int, lines: Sequence[LayoutLine]) -> bool:
    """Plausible web/institutional reference start without classical author-year form."""
    if index < 0 or index >= len(lines):
        return False
    current = lines[index].text.strip()
    if not current or current[:1].islower():
        return False
    if (
        access_metadata_continuation(index, lines)
        or embedded_access_metadata_continuation(index, lines)
        or source_with_link_continuation(index, lines)
    ):
        return False
    # A journal/source continuation that merely contains a DOI/URL is not a
    # standalone web reference start.
    if SOURCE_CONTINUATION_RX.match(current) or SOURCE_VOLUME_PAGE_RX.search(current) or JOURNAL_YEAR_VOLUME_CONTINUATION_RX.match(current) or journal_volume_pages_link_continuation(index, lines):
        return False
    # Same-line web resource with access metadata: ``About IBC https://... (Accessed...)``.
    # Exclude pure continuation labels such as ``Disponível em:``, ``Retrieved from``
    # and lines whose URL itself is the first token.
    meta_prefix = re.match(r"^(?:<?https?://|www\.|dispon[ií]vel\s+em|available\s+(?:at|from)|retrieved\s+from|acesso\s+em|accessed\b)", current, re.I)
    if not meta_prefix and WEB_ACCESS_RX.search(current) and ("http" in current.lower() or "www." in current.lower()):
        url_pos = min([pos for pos in [current.lower().find("http"), current.lower().find("www.")] if pos >= 0], default=-1)
        prefix_words = current[:url_pos].strip(" <:,;-").split() if url_pos >= 0 else []
        if 2 <= len(prefix_words) <= 10:
            return True
    # Institutional lead followed by colon, with URL/access evidence in the next
    # physical line. This covers forms such as ``Europe commission: ...``.
    if INSTITUTION_COLON_RX.match(current) and index + 1 < len(lines):
        following = lines[index + 1].text.strip()
        name = INSTITUTION_COLON_RX.match(current).group("name")
        previous = lines[index - 1].text.strip() if index > 0 else ""
        previous_connector = bool(previous and (previous.endswith((",", ":", "-", "–", "—")) or re.search(r"\b(?:in|en|of|de|and|for|to|y|e|et)\s*$", previous, re.I)))
        if WEB_ACCESS_RX.search(following) and not previous_connector:
            nwords = len(name.split())
            if 1 <= nwords <= 8 and name[:1].isupper():
                return True
    return False




def _top_level_comma_split(text: str) -> tuple[str, str] | None:
    """Split on the first comma outside (), [] and {}."""
    stack = []
    pairs = {')': '(', ']': '[', '}': '{'}
    opens = set(pairs.values())
    for i, ch in enumerate(str(text)):
        if ch in opens:
            stack.append(ch)
        elif ch in pairs and stack and stack[-1] == pairs[ch]:
            stack.pop()
        elif ch == ',' and not stack:
            return str(text)[:i].strip(), str(text)[i + 1:].strip()
    return None


def _person_name_word(token: str) -> bool:
    raw = str(token).strip(" .()[]{}")
    if not raw or any(ch.isdigit() for ch in raw):
        return False
    pieces = [p for p in re.split(r"[-'’]", raw) if p]
    return bool(pieces and all(piece[:1].isupper() and all(ch.isalpha() for ch in piece) for piece in pieces))


def _surname_clause(text: str) -> bool:
    raw = str(text).strip()
    if not raw or any(ch in raw for ch in "[](){}") or PERSON_LEAD_STOP_RX.match(raw):
        return False
    words = raw.split()
    return bool(1 <= len(words) <= 3 and all(_person_name_word(word) for word in words))


def _given_clause(text: str) -> bool:
    raw = re.sub(r"\s*\((?i:ed|eds|editor|editors|trans)\.?\)\s*$", "", str(text).strip()).strip()
    if not raw or any(ch.isdigit() for ch in raw):
        return False
    if re.fullmatch(r"(?:[A-ZÁÉÍÓÚÑ]\.\s*){1,5}", raw):
        return True
    tokens = raw.split()
    # One full given name, optionally accompanied by initials (J. Kabaddi / Dora A.).
    full = [tok for tok in tokens if not re.fullmatch(r"(?:[A-ZÁÉÍÓÚÑ]\.)+", tok)]
    initials = [tok for tok in tokens if re.fullmatch(r"(?:[A-ZÁÉÍÓÚÑ]\.)+", tok)]
    return bool(len(full) == 1 and _person_name_word(full[0]) and len(initials) <= 3 and len(tokens) <= 4)


def strong_comma_person_lead(text: str) -> bool:
    """Person morphology such as ``Surname, P.J., Title`` or ``Surname, Given, Title``."""
    raw = str(text).strip()
    split = _top_level_comma_split(raw)
    if not split:
        return False
    surname, remainder = split
    if not _surname_clause(surname):
        return False
    split2 = _top_level_comma_split(remainder)
    if not split2:
        return False
    given, body = split2
    given = given.strip(); body = body.strip()
    if not _given_clause(given) or not body:
        return False
    if re.match(r"^(?:18|19|20)\d{2}|^(?:https?://|www\.|doi\b)", body, re.I):
        return False
    if re.match(r"^(?:v\.?|vol\.?|volume|n\.?|no\.?|issue|pp?\.?)\s*\d", body, re.I):
        return False
    # Place/state continuation: ``Perspectives, Albany, NY, ...`` is not a person.
    if re.match(r"^[A-Z]{2,3}\s*(?:,|$)", body):
        return False
    return len(re.findall(r"[^\W\d_]+", body, re.UNICODE)) >= 2


def initial_first_person_lead(text: str) -> bool:
    """Initial-first person author such as ``S.M. Assad, Title``."""
    return bool(INITIAL_FIRST_PERSON_RX.match(str(text).strip()))


def strong_person_author_date(text: str) -> bool:
    """Canonical person/date morphology stronger than generic comma + year."""
    raw = str(text).strip()
    if initial_first_person_lead(raw) and (YEAR_RX.search(raw) or SIN_FECHA_RX.search(raw) or UNDATED_RX.search(raw)):
        return True
    split = _top_level_comma_split(raw)
    if not split:
        return False
    surname, remainder = split
    if not _surname_clause(surname):
        return False
    date = YEAR_RX.search(remainder) or SIN_FECHA_RX.search(remainder) or UNDATED_RX.search(remainder)
    if not date or date.start() > 180:
        return False
    before = remainder[:date.start()].strip(" \t,;:()[]")
    if not before:
        return False
    if re.search(r"\b(?:v\.?|vol\.?|volume|n\.?|no\.?|issue|pp?\.?|pages?|press|publishers?|journal|revista|review)\s*\d?", before, re.I):
        return False
    # Only the first inverted author's given-name clause is needed to establish
    # person morphology. This supports ``Robert & Biklen, Sari... (1982)`` and
    # similar multi-author forms without treating a journal/source phrase as a person.
    first_piece = re.split(r"\s+(?:&|and|y|e)\s+|,", before, maxsplit=1, flags=re.I)[0]
    first_piece = first_piece.strip(" \t,;:()[]")
    if _given_clause(first_piece):
        return True
    # Two full capitalized given/middle names are also common (``Agus Udong``).
    toks = [tok.strip(" .") for tok in first_piece.split() if tok.strip(" .")]
    return bool(1 <= len(toks) <= 2 and all(_person_name_word(tok) for tok in toks))


def institutional_comma_title_lead(text: str) -> bool:
    """Institutional author followed by a comma and title/body material."""
    raw = str(text).strip()
    split = _top_level_comma_split(raw)
    if not split:
        return False
    lead, body = split
    if not lead or not body or len(lead) > 150 or any(ch in lead for ch in "]}"):
        return False
    if not INSTITUTION_TITLE_LEAD_RX.search(lead):
        return False
    if SOURCE_NAME_STOP_RX.search(lead) or re.search(r"\b(?:press|publishers?|publishing|editorial|editora)\s*$", lead, re.I):
        return False
    if re.match(r"^(?:18|19|20)\d{2}|^(?:https?://|www\.|doi\b)", body, re.I):
        return False
    return len(body.split()) >= 3


def late_author_title_start(index: int, lines: Sequence[LayoutLine]) -> bool:
    """Open-set author/title start whose date/source may occur on later lines."""
    if index < 0 or index >= len(lines):
        return False
    raw = lines[index].text.strip()
    if not raw or DOI_OR_URL_RX.match(raw):
        return False
    if not (strong_comma_person_lead(raw) or initial_first_person_lead(raw) or institutional_comma_title_lead(raw)):
        return False
    page = lines[index].page
    neighborhood = ' '.join(
        line.text.strip() for line in lines[index:min(len(lines), index + 4)]
        if line.page <= page + 1
    )
    return bool(
        YEAR_RX.search(neighborhood) or SIN_FECHA_RX.search(neighborhood) or UNDATED_RX.search(neighborhood)
        or DOI_OR_URL_RX.search(neighborhood)
        or re.search(r"\b(?:ph\.?d\.?|thesis|dissertation|press|publishers?|university|journal|review|vol\.?|volume|pp?\.?|whitepaper|article)\b", neighborhood, re.I)
    )


def title_led_reference_start(index: int, lines: Sequence[LayoutLine]) -> bool:
    """Anonymous/title-led web or media item with independent nearby metadata."""
    if index < 0 or index >= len(lines):
        return False
    raw = lines[index].text.strip()
    if not re.match(r"^[‘’“\"']", raw):
        return False
    if ',' not in raw or len(raw.split()) < 3:
        return False
    neighborhood = ' '.join(line.text.strip() for line in lines[index:min(len(lines), index + 3)])
    if not (DOI_OR_URL_RX.search(neighborhood) or YEAR_RX.search(neighborhood) or re.search(r"\baccessed\b", neighborhood, re.I)):
        return False
    if index > 0:
        prev = lines[index - 1].text.strip()
        if not _previous_looks_complete(prev) and re.search(r"[‘“\"]", prev) and not re.search(r"[’”\"]", prev):
            return False
    return True


def wrapped_editor_list_continuation(index: int, lines: Sequence[LayoutLine]) -> bool:
    """Editor/author list wrapped after an ``In ...`` clause."""
    if index <= 0 or index >= len(lines):
        return False
    current = lines[index].text.strip()
    previous = lines[index - 1].text.strip()
    if _previous_looks_complete(previous):
        return False
    if not re.search(r"\((?:ed|eds|editors?)\.?\)", current[:120], re.I):
        return False
    return bool(re.search(r"\b(?:in|en|em)\.?\s+[A-ZÁÉÍÓÚÑ]\.\s+[A-ZÁÉÍÓÚÀÂÊÔÃÕÇÜÑ][\w'’\-]*\s*$", previous, re.I))


def editor_clause_continuation(index: int, lines: Sequence[LayoutLine]) -> bool:
    """Editor name continuing an ``in X.`` source clause across physical lines."""
    if index <= 0 or index >= len(lines):
        return False
    current = lines[index].text.strip()
    previous = lines[index - 1].text.strip()
    return bool(EDITOR_TAIL_RX.match(current) and re.search(r"\b(?:in|en|em)\s+[A-ZÁÉÍÓÚÑ]\.\s*$", previous, re.I))


def late_source_tail_continuation(index: int, lines: Sequence[LayoutLine]) -> bool:
    """Late-date/source fragment completing the previous physical record."""
    if index <= 0 or index >= len(lines):
        return False
    current = lines[index].text.strip()
    previous = lines[index - 1].text.strip()
    if not current or not previous:
        return False
    # Same-line named web resources whose link precedes access metadata are
    # independent starts even after a subsection heading ending in a colon.
    first_link = DOI_OR_URL_RX.search(current)
    access = ACCESS_METADATA_EMBEDDED_RX.search(current)
    if first_link and first_link.start() > 0:
        prefix_words = current[:first_link.start()].strip(" <:,;-").split()
        previous_heading_like = bool(previous.endswith(":") and len(previous.split()) <= 5)
        if 2 <= len(prefix_words) <= 12 and (not access or first_link.start() < access.start()) and (previous_heading_like or _previous_looks_complete(previous)):
            return False
    if wrapped_editor_list_continuation(index, lines) or editor_clause_continuation(index, lines):
        return True
    # An institutional line bridging an unfinished author record to retrieval
    # metadata is a continuation (e.g. affiliation/title then Retrieved URL).
    if previous.endswith(',') and institutional_comma_title_lead(current) and index + 1 < len(lines):
        following = lines[index + 1].text.strip()
        if DOI_OR_URL_RX.search(following) or ACCESS_METADATA_PREFIX_RX.match(following):
            return True
    if strong_person_author_date(current) or late_author_title_start(index, lines) or title_led_reference_start(index, lines):
        return False
    if NUMERIC_MARKER_RX.match(current):
        return False
    if _previous_looks_complete(previous):
        return False
    has_date_or_link = bool(YEAR_RX.search(current) or DOI_OR_URL_RX.search(current) or UNDATED_RX.search(current))
    tail_lexical = bool(
        SOURCE_TAIL_LEAD_RX.match(current)
        or SOURCE_ABBREVIATION_RX.search(current)
        or THESIS_CONTINUATION_RX.search(current)
        or PUBLISHERISH_RX.search(current)
        or DOI_OR_URL_RX.search(current)
    )
    connector = previous.endswith((',', ':', '-', '–', '—', '/'))
    source_body = bool(SOURCE_ABBREVIATION_RX.search(current) and YEAR_RX.search(current))
    return bool((has_date_or_link and tail_lexical) or (connector and (has_date_or_link or source_body)))


def _author_fragment_count(text: str) -> int:
    return len(AUTHOR_FRAGMENT_RX.findall(str(text)))


def long_author_list_fragment(text: str) -> bool:
    """Author-list physical line likely to continue before the bibliographic date."""
    raw = str(text).strip()
    if not raw or YEAR_RX.search(raw) or SIN_FECHA_RX.search(raw):
        return False
    count = _author_fragment_count(raw)
    commas = raw.count(',')
    return bool(count >= 4 or (count >= 2 and commas >= 6))


def author_title_start(index: int, lines: Sequence[LayoutLine]) -> bool:
    """Person-author + title start where the year/source may occur on later lines.

    Covers MLA-like ``Surname, Given. Title...`` records without assuming MLA as
    a named style.  A person morphology plus a following title and nearby
    bibliographic evidence are all required.
    """
    if index < 0 or index >= len(lines):
        return False
    raw = lines[index].text.strip()
    if not raw or DOI_OR_URL_RX.match(raw) or PUBLISHER_WORD_YEAR_RX.match(raw):
        return False
    match = AUTHOR_TITLE_START_RX.match(raw) or ET_AL_AUTHOR_TITLE_RX.match(raw)
    if not match:
        # Open-set multi-author form: ``Surname, Given ..., and Given Surname. Title``.
        # The author clause must be person-like, digit-free and end before a
        # capitalized/quoted title.
        lead = re.match(rf"^(?:{PERSON_SURNAME}(?:\s+{PERSON_SURNAME}){{0,2}}),\s*(?P<body>.{{3,115}}?)\.\s+(?=[‘’“\"']?[A-ZÁÉÍÓÚÀÂÊÔÃÕÇÜÑ])", raw)
        if lead:
            body = lead.group('body')
            proper_tokens = re.findall(PERSON_NAME_WORD, body)
            if not re.search(r"\d", body) and len(proper_tokens) >= 2 and re.search(r"(?:,|\band\b|&|\by\b|\be\b)", body, re.I):
                match = lead
    if not match:
        return False
    # Location/access tails can mimic ``Surname, Given. Title`` superficially
    # (e.g. ``Columbia, Canada. Retrieved from``).  Access metadata is not a
    # plausible title lead for a person-authored record.
    tail = raw[match.end():].lstrip(" ‘’\"\'")
    if re.match(r'^(?:retrieved|retrived|available|accessed|disponible|dispon[ií]vel|consultado|recuperado)\b', tail, re.I):
        return False
    # Require evidence shortly after the physical start.  This prevents generic
    # prose of the form ``Surname, Given. Sentence...`` from becoming a boundary.
    page = lines[index].page
    neighborhood = ' '.join(
        line.text.strip() for line in lines[index:min(len(lines), index + 4)]
        if line.page <= page + 1
    )
    return bool(
        YEAR_RX.search(neighborhood)
        or SIN_FECHA_RX.search(neighborhood)
        or DOI_OR_URL_RX.search(neighborhood)
        or re.search(r"\b(?:vol\.?|volume|issue|no\.?|pp?\.?|press|publishers?|university|journal|review|thesis|dissertation)\b", neighborhood, re.I)
    )


def punctuation_inherited_author_start(index: int, lines: Sequence[LayoutLine]) -> bool:
    """PDF-degraded repeated-author mark such as ``. (1995). Title``."""
    if index <= 0 or index >= len(lines):
        return False
    current = lines[index].text.strip()
    if not PUNCTUATION_INHERITED_DATE_RX.match(current):
        return False
    # Require a real preceding bibliographic record and title material after date.
    tail = PUNCTUATION_INHERITED_DATE_RX.sub('', current, count=1).strip(' .')
    return bool(lines[index - 1].text.strip() and len(tail.split()) >= 3 and tail[:1].isupper())


def compact_person_author_year_start(text: str) -> bool:
    """Compact person form such as ``Cajander AK. 1926`` or ``Bowen GD. 1970``."""
    raw = str(text).strip()
    if not raw or DOI_OR_URL_RX.match(raw):
        return False
    return bool(COMPACT_PERSON_AUTHOR_YEAR_RX.match(raw))


def journal_volume_pages_link_continuation(index: int, lines: Sequence[LayoutLine]) -> bool:
    """Journal/source tail carrying volume-pages plus DOI/URL.

    Besides a pure source line, admit a hybrid title-tail + journal line only
    when the preceding physical line is visibly incomplete (connector, comma,
    colon, or hyphen).
    """
    if index <= 0 or index >= len(lines):
        return False
    current = lines[index].text.strip()
    previous = lines[index - 1].text.strip()
    if JOURNAL_VOLUME_PAGES_LINK_RX.match(current) or VOLUME_PAGES_IDENTIFIER_RX.match(current):
        return True
    has_link = bool(DOI_OR_URL_RX.search(current))
    has_volume_pages = bool(re.search(r"\b\d{1,4}\s*:\s*\d{1,6}\s*[-–—]\s*\d{1,6}\b", current))
    previous_incomplete = bool(
        previous.endswith((",", ":", "-", "–", "—"))
        or re.search(r"\b(?:in|en|of|de|and|y|e|et)\s*$", previous, re.I)
    )
    return bool(has_link and has_volume_pages and previous_incomplete)


def wrapped_author_continuation(index: int, lines: Sequence[LayoutLine]) -> bool:
    if index <= 0:
        return False
    current = lines[index].text.strip()
    previous = lines[index - 1].text.strip()
    current_has_date = bool(YEAR_RX.search(current) or SIN_FECHA_RX.search(current))
    if not current_has_date:
        return False

    # v0.8.9: a long author list may end at the physical line break and the
    # bibliography year may begin the next line together with the title, e.g.
    # ``... Vanderhammen, T.`` -> ``1993. Absolute chronology ...``.  This is
    # distinct from an inherited-author date-only entry: require a bare leading
    # year *plus title/body text* and strong author-list morphology immediately
    # before it.
    if re.match(r"^(?:18|19|20)\d{2}[a-z]?\.\s+\S+(?:\s+\S+){1,}", current):
        if long_author_list_fragment(previous) or (MANY_AUTHOR_TOKENS_RX.search(previous) and len(AUTHOR_INITIAL_RX.findall(previous)) >= 2):
            return True

    # Strong pattern: an author list is broken immediately before its final
    # author(s), followed by the date on the current physical line.
    if AUTHOR_LIST_END_RX.search(previous) and "," in current:
        return True
    # v0.8.6: accept both ``Surname I.`` and ``Surname, I.`` author-token forms;
    # PDF extraction often mixes them inside the same list.
    if long_author_list_fragment(previous):
        return bool(_author_fragment_count(current) >= 1 or current.count(',') >= 2)
    return False


def wrapped_author_start(index: int, lines: Sequence[LayoutLine]) -> bool:
    """Detect the first physical line of an author list whose date is later."""
    if index < 0 or index >= len(lines) - 1:
        return False
    current = lines[index].text.strip()
    following = lines[index + 1].text.strip()
    if not current or YEAR_RX.search(current) or SIN_FECHA_RX.search(current):
        return False
    authorish = bool(
        AUTHOR_LIST_END_RX.search(current)
        or long_author_list_fragment(current)
    )
    if not authorish:
        return False
    if wrapped_author_continuation(index + 1, lines):
        return True
    return bool(
        parenthetical_author_year(following)
        or particle_author_date(following)
        or re.match(r"^(?:[A-ZÁÉÍÓÚÑ][^,]{0,60},\s*)?(?:&|and|y|e)?\s*[A-ZÁÉÍÓÚÑ][^()]{0,90}\((?:18|19|20)\d{2}", following, re.I)
        or re.match(r"^\((?:18|19|20)\d{2}[a-z]?\)", following)
    )


def numeric_page_continuation(index: int, lines: Sequence[LayoutLine]) -> bool:
    if index <= 0:
        return False
    current = lines[index].text.strip()
    previous = lines[index - 1].text.strip()
    if not NUMERIC_MARKER_RX.match(current):
        return False
    if not PAGE_DOI_CONTINUATION_RX.match(current):
        return False
    # Page/identifier tail split across PDF lines: ``509-`` / ``521. doi:...``.
    if previous.endswith(("-", "–", "—")):
        return True
    # v0.8.9: some author-year references break immediately after a journal
    # issue comma, leaving ``89. http://doi...`` on its own physical line.
    # Require an incomplete punctuation tail plus bibliographic evidence in the
    # previous line. Strong numeric regimes are protected later in scoring so
    # a genuine numbered web reference ``89. http://...`` remains a boundary.
    if previous.endswith((",", ";")) and (YEAR_RX.search(previous) or SOURCE_VOLUME_PAGE_RX.search(previous)):
        return True
    return False


def wrapped_date_continuation(index: int, lines: Sequence[LayoutLine]) -> bool:
    """Date-only physical line that completes a wrapped author list."""
    if index <= 0:
        return False
    current = lines[index].text.strip()
    previous = lines[index - 1].text.strip()
    if not re.match(r"^\((?:18|19|20)\d{2}[a-z]?(?:\s*[-–—]\s*(?:18|19|20)?\d{2})?\)", current):
        return False
    return bool(
        AUTHOR_LIST_END_RX.search(previous)
        or (MANY_AUTHOR_TOKENS_RX.search(previous) and len(AUTHOR_INITIAL_RX.findall(previous)) >= 2)
    )


def publisher_year_continuation(index: int, lines: Sequence[LayoutLine]) -> bool:
    if index <= 0:
        return False
    current = lines[index].text.strip()
    previous = lines[index - 1].text.strip()
    if not PUBLISHER_YEAR_CONTINUATION_RX.match(current):
        return False
    # A compact publisher lexical tail after an incomplete physical line is a
    # high-specificity continuation (``CPT`` / ``Press, 2009.``).
    if PUBLISHER_WORD_YEAR_RX.match(current) and previous and not _previous_looks_complete(previous):
        return True
    # Strongest legacy forms: slash/colon split, or a location/imprint clause in
    # the preceding physical line.
    return bool(
        previous.endswith(("/", ":", ";"))
        or re.search(r"[A-ZÁÉÍÓÚÀÂÊÔÃÕÇÜÑ][^:]{1,50}:\s*[^.;]{1,80}$", previous)
    )


def conference_event_continuation(index: int, lines: Sequence[LayoutLine]) -> bool:
    if index <= 0:
        return False
    current = lines[index].text.strip()
    previous = lines[index - 1].text.strip()
    return bool(
        CONFERENCE_CONTINUATION_RX.match(current)
        and (re.search(r"\b(?:in|em)\s*:\s*", previous, re.I) or previous.rstrip().endswith(","))
    )


def late_year_after_incomplete_previous(index: int, lines: Sequence[LayoutLine]) -> bool:
    if index <= 0:
        return False
    current = lines[index].text.strip()
    previous = lines[index - 1].text.strip()
    if _previous_looks_complete(previous):
        return False
    # A named web resource with its URL/access date on the same line can be a
    # complete reference start after a subsection heading ending in colon.
    if WEB_ACCESS_RX.search(current) and ("http" in current.lower() or "www." in current.lower()):
        url_pos = min([pos for pos in [current.lower().find("http"), current.lower().find("www.")] if pos >= 0], default=-1)
        if url_pos > 0 and len(current[:url_pos].strip(" <:,;-").split()) >= 2:
            return False
    m = YEAR_RX.search(current)
    if not m or m.start() < 18:
        return False
    # Do not suppress strong canonical starts just because the preceding record
    # omitted terminal punctuation. Generic comma/year and one-word institutional
    # matches are insufficient here because wrapped source tails can mimic them.
    if strong_person_author_date(current) or late_author_title_start(index, lines) or particle_author_date(current) or dot_initial_author_date(current) or undated_author_start(current):
        return False
    if institutional_author_date(current) and not (PUBLISHERISH_RX.match(current) or previous.endswith(("-", "–", "—", "/"))):
        return False
    # ``Surname, Initial. 2020`` remains a plausible person start.
    if re.match(r"^[^,]{1,70},\s*[A-ZÁÉÍÓÚÑ](?:\.|\b)", current):
        return False
    return True


def source_metadata_continuation(index: int, lines: Sequence[LayoutLine]) -> bool:
    if index <= 0:
        return False
    current = lines[index].text.strip()
    previous = lines[index - 1].text.strip()
    # Strong person grammars outrank generic source-role regexes unless this is
    # explicitly the second physical line of a wrapped author list.
    if (strong_person_author_date(current) or compact_person_author_year_start(current) or author_title_start(index, lines) or late_author_title_start(index, lines) or title_led_reference_start(index, lines)) and not wrapped_author_continuation(index, lines):
        return False
    if thesis_metadata_continuation(index, lines):
        return True
    if split_location_publisher_continuation(index, lines):
        return True
    if quoted_title_continuation(index, lines):
        return True
    if lowercase_source_continuation(index, lines):
        return True
    if source_with_link_continuation(index, lines):
        return True
    if journal_volume_pages_link_continuation(index, lines):
        return True
    if late_source_tail_continuation(index, lines):
        return True
    if late_year_after_incomplete_previous(index, lines):
        return True
    if SOURCE_CONTINUATION_RX.match(current) or JOURNAL_YEAR_VOLUME_CONTINUATION_RX.match(current):
        return True
    # Publisher imprint split across physical lines, e.g.
    # ``Ribeirão Preto: Legis /`` -> ``Summa, 2015.``
    if publisher_year_continuation(index, lines):
        return True
    # Conference/event titles in all caps after an ``In:`` continuation can
    # resemble ABNT uppercase authors but are source metadata.
    if conference_event_continuation(index, lines):
        return True
    # Journal/publisher continuation with volume/number/pages and a late year,
    # but without person-author initials immediately after the first comma.
    if (
        SOURCE_VOLUME_PAGE_RX.search(current)
        and YEAR_RX.search(current)
        and "," in current
        and not AUTHOR_INITIAL_AFTER_COMMA_RX.match(current)
    ):
        return True
    if ABNT_SOURCE_CONTINUATION_RX.match(current):
        return True
    # Colon-led location/publisher lines (e.g. "PR: Universidade..., 2011") are
    # not new authors even when they contain a late year.
    if re.match(r"^[A-Z]{2}:\s+(?:Universidade|University|Editora|Editorial)\b", current, re.I):
        return True
    # Named programs/series followed by thesis/source metadata and a year are
    # continuations unless a clear author-date signature exists.
    if re.match(r"^[A-ZÁÉÍÓÚÀÂÊÔÃÕÇÜÑ][A-ZÁÉÍÓÚÀÂÊÔÃÕÇÜÑ\- ]{3,35}:\s+", current) and YEAR_RX.search(current):
        if not (parenthetical_author_year(current) or particle_author_date(current)):
            return True
    if previous.endswith(":") and YEAR_RX.search(current) and SOURCE_VOLUME_PAGE_RX.search(current):
        if not AUTHOR_INITIAL_AFTER_COMMA_RX.match(current):
            return True
    return False


def probable_author_without_date(text: str) -> bool:
    """Strong start cue for backward expansion, especially ABNT records."""
    raw = text.strip()
    if not raw or DOI_OR_URL_RX.match(raw):
        return False
    # Uppercase surname/institution followed by comma is common in ABNT.
    if re.match(r"^[A-ZÁÉÍÓÚÀÂÊÔÃÕÇÜÑ][A-ZÁÉÍÓÚÀÂÊÔÃÕÇÜÑ'’\- ]{1,70},\s+", raw):
        return True
    # Particle surname followed by comma can also begin without an immediate date.
    if PARTICLE_AUTHOR_RX.match(raw):
        return True
    return False


def backward_expansion_start(lines: Sequence[LayoutLine], start_page: int, start_y: float) -> Dict:
    """Find a controlled earlier author-like start above a discovered region.

    The search is same-page and limited to 170 PDF points.  A candidate must be
    a strong author-like line without relying on a generic year and must be
    followed shortly by bibliographic evidence.  This deliberately does not
    absorb free prose below a REFERENCES heading.
    """
    prior = [
        (idx, line) for idx, line in enumerate(lines)
        if int(line.page) == int(start_page)
        and float(line.y0) < float(start_y)
        and float(start_y) - float(line.y0) <= 170.0
        and line.text.strip()
    ]
    prior.sort(key=lambda pair: float(pair[1].y0))
    candidates = []
    for idx, line in prior:
        is_author = probable_author_without_date(line.text)
        is_numeric = bool(NUMERIC_MARKER_RX.match(line.text.strip()))
        if not (is_author or is_numeric):
            continue
        later = [
            cand.text for cand in lines[idx: min(len(lines), idx + 6)]
            if int(cand.page) == int(start_page)
        ]
        joined = " ".join(later)
        if YEAR_RX.search(joined) or SIN_FECHA_RX.search(joined) or DOI_OR_URL_RX.search(joined):
            candidates.append(line)
    if not candidates:
        return {"expanded": False, "start_y": float(start_y), "reason": "no_strong_prior_author_start"}
    first = min(candidates, key=lambda line: float(line.y0))
    return {
        "expanded": True,
        "start_y": float(first.y0),
        "original_start_y": float(start_y),
        "reason": "strong_prior_author_start_with_nearby_bibliographic_evidence",
        "text_preview": first.text.strip()[:180],
    }
