"""Bibliographic continuation-role diagnostics for v0.8.5-l.

The classifier describes *what a physical line is doing inside a reference*.
It does not decide boundaries by itself.  Scoring uses the role only after
checking whether the line has a strong independent start signature.
"""
from __future__ import annotations
import re
from typing import Dict, Sequence
from biblioref.legacy.engine import LayoutLine, YEAR_RX, SIN_FECHA_RX
from biblioref.detection.signals import parenthetical_author_year
from biblioref.adaptive.continuity import (
    institutional_author_date, dot_initial_author_date, reference_with_access_metadata_start,
    source_with_link_continuation, author_title_start, compact_person_author_year_start,
    journal_volume_pages_link_continuation, publisher_year_continuation,
    late_author_title_start, title_led_reference_start, strong_person_author_date,
    late_source_tail_continuation,
)

URL_RX = re.compile(r"(?:https?://|www\.|\bdoi\b|10\.\d{4,9}/)", re.I)
YEAR_ANY_RX = re.compile(r"\b(?:18|19|20)\d{2}[a-z]?\b", re.I)
ACCESS_RX = re.compile(r"\b(?:retrieved(?:\s+\w+){0,5}\s+from|available\s+(?:at|from)|accessed(?:\s+on)?|recuperad[oa]\s+(?:de|en)|dispon[ií]vel\s+em|disponible\s+en|acesso\s+em|consultad[oa]\s+en)\b", re.I)
MONTH_RX = re.compile(r"\b(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre|january|february|march|april|may|june|july|august|september|october|november|december)\b", re.I)
REVISION_RX = re.compile(r"^(?:modificad[oa]|reformad[oa]|actualizad[oa]|aprobado|aprobada|revised|amended|updated)\b", re.I)
JOURNAL_META_RX = re.compile(r"(?:\b(?:revista|journal|proceedings|actas?|vol\.?|volume|issue|n[úu]m\.?|no\.?|pp?\.?)\b|\(\d{1,4}\)\s*,?\s*\d{1,5}\s*[-–—]\s*\d{1,5})", re.I)
JOURNAL_NAME_RX = re.compile(r"^(?:revista\b|journal\b|polis\s+revista\b|desacatos\b|sociales\b)", re.I)
LOCATION_PUBLISHER_RX = re.compile(r"^[A-ZÁÉÍÓÚÀÂÊÔÃÕÇÜÑ][A-Za-zÁÉÍÓÚÀÂÊÔÃÕÇÜÑáéíóúàâêôãõçüñ .'-]{1,45}:\s*[^.]{1,80},\s*(?:18|19|20)\d{2}\.?$", re.I)
THESIS_WORD_RX = re.compile(r"\b(?:tesis|thesis|disserta(?:ç|c)[aã]o|monograf[ií]a|tcc|trabajo\s+final|para\s+optar\s+por\s+el\s+t[ií]tulo)\b", re.I)
INSTITUTION_LOCATION_RX = re.compile(r"^(?:universidad|universidade|university|facultad|faculty|instituto|institute)\b.*\b(?:18|19|20)\d{2}\.?$", re.I)
CONFERENCE_RX = re.compile(r"\b(?:congres[os]|congress|conference|symposium|simposio|encontro\s+nacional|encuentro\s+nacional|proceedings|actas?)\b", re.I)
DATE_ONLY_RX = re.compile(r"^\(\s*(?:18|19|20)\d{2}[a-z]?\s*\)\s*[.]?", re.I)
LEGAL_START_RX = re.compile(r"^(?:acordada|ley|decreto|resoluci[oó]n|ordenanza|c[oó]digo\s+(?:penal|civil|de\s+[ée]tica)|reglamento)\b", re.I)
DOCUMENT_TITLE_RX = re.compile(r"^(?:c[oó]digo\s+de\s+[ée]tica|code\s+of\s+ethics|manual\b|guideline\b|directriz\b|reglamento\b|protocolo\b)", re.I)
INSTITUTION_ACCESS_START_RX = re.compile(r"^[A-Z][^\n]{3,120}\.\s*(?:18|19|20)\d{2}\.\s*(?:Available|Retrieved|Accessed)\s*:?$", re.I)
INSTITUTION_ACRONYM_ACCESS_RX = re.compile(r"^[A-ZÁÉÍÓÚ0-9.\-]{2,15},\s+[^\n]{3,100}\.\s*(?i:Dispon[ií]vel\s+em|Disponible\s+en|Available\s+(?:at|from)|Retrieved\s+from|Accessed)\b")


def _window(lines: Sequence[LayoutLine], start: int, end: int) -> str:
    return " ".join(lines[i].text.strip() for i in range(max(0,start), min(len(lines),end)) if lines[i].text.strip())


def _previous_is_incomplete_author_list(text: str) -> bool:
    raw = str(text).strip()
    if not raw or not raw.endswith((",", "&")):
        return False
    initials = len(re.findall(r"\b[A-Z]\.(?:-[A-Z]\.)?", raw))
    separators = len(re.findall(r"[,;&]|\band\b|\by\b|\be\b", raw, re.I))
    return bool(initials >= 2 and separators >= 3 and not YEAR_ANY_RX.search(raw))


def classify_continuation_role(index: int, lines: Sequence[LayoutLine]) -> Dict:
    text = lines[index].text.strip()
    prev = lines[index-1].text.strip() if index > 0 else ""
    prev2 = _window(lines, index-2, index)
    nxt = lines[index+1].text.strip() if index+1 < len(lines) else ""
    roles=[]; evidence=[]

    # Explicit start protectors: these are real record grammars that happen to
    # contain words otherwise common in metadata continuations.
    start_protected = False
    start_kind = None
    if reference_with_access_metadata_start(index, lines):
        start_protected=True; start_kind='reference_with_access_metadata'; evidence.append('independent_start_before_access_metadata')
    elif LEGAL_START_RX.match(text) and YEAR_ANY_RX.search(text):
        start_protected=True; start_kind='legal_document'; evidence.append('legal_document_with_date')
    elif INSTITUTION_ACCESS_START_RX.match(text):
        start_protected=True; start_kind='institutional_web'; evidence.append('institution_year_before_access_keyword')
    elif INSTITUTION_ACRONYM_ACCESS_RX.match(text) and (URL_RX.search(text) or URL_RX.search(nxt)):
        start_protected=True; start_kind='institutional_web'; evidence.append('institution_acronym_access_with_url')
    elif DOCUMENT_TITLE_RX.match(text) and (YEAR_ANY_RX.search(nxt) or SIN_FECHA_RX.search(nxt)):
        start_protected=True; start_kind='institutional_document_late_date'; evidence.append('document_title_with_date_on_next_line')

    # Continuation families.
    if REVISION_RX.match(text) and YEAR_ANY_RX.search(text):
        roles.append('document_revision'); evidence.append('revision_or_amendment_with_date')
    if source_with_link_continuation(index, lines):
        roles.append('source_with_link'); evidence.append('publisher_or_source_tail_with_link')
    if journal_volume_pages_link_continuation(index, lines):
        roles.append('journal_volume_pages_link'); evidence.append('journal_volume_pages_with_identifier_tail')
    if publisher_year_continuation(index, lines):
        roles.append('publisher_year_tail'); evidence.append('publisher_imprint_plus_year_after_incomplete_line')
    if late_source_tail_continuation(index, lines):
        roles.append('late_source_tail'); evidence.append('late_date_or_identifier_source_tail_after_incomplete_line')
    if ACCESS_RX.search(text) and (URL_RX.search(text) or URL_RX.search(nxt)):
        # If the URL is already present *before* an Accessed/Retrieved suffix, the
        # line is commonly a complete web-resource record (``About IBC URL
        # (Accessed...)``), not metadata continuing a prior reference.
        access_match = ACCESS_RX.search(text)
        first_link = URL_RX.search(text)
        link_precedes_access = bool(first_link and access_match and first_link.start() < access_match.start())
        # If the line itself starts with a strong start signature, the access
        # phrase belongs to that new reference, not the previous one.
        if not start_protected and not link_precedes_access:
            roles.append('access_metadata'); evidence.append('access_phrase_with_url_nearby')
    if re.match(r"^\d{1,2}\s+de\s+", text, re.I) and MONTH_RX.search(text) and URL_RX.search(text):
        roles.append('access_date'); evidence.append('calendar_access_date_with_url')
    if LOCATION_PUBLISHER_RX.match(text):
        roles.append('location_publisher'); evidence.append('location_colon_publisher_year')
    if THESIS_WORD_RX.search(prev2) and INSTITUTION_LOCATION_RX.match(text):
        roles.append('thesis_institution'); evidence.append('institution_after_thesis_or_monograph')
    if CONFERENCE_RX.search(text) and YEAR_ANY_RX.search(text) and index > 0:
        roles.append('conference_source'); evidence.append('event_name_location_year_after_prior_content')
    if JOURNAL_NAME_RX.match(text) and (JOURNAL_META_RX.search(text) or ACCESS_RX.search(text) or URL_RX.search(text)):
        roles.append('journal_source'); evidence.append('journal_name_with_issue_access_or_identifier')
    elif JOURNAL_META_RX.search(text) and (URL_RX.search(text) or re.search(r"\b\d{1,5}\s*[-–—]\s*\d{1,5}\b", text)) and index > 0:
        roles.append('journal_metadata'); evidence.append('issue_pages_or_identifier_without_author_signature')
    if text[:1].islower() and THESIS_WORD_RX.search(text):
        roles.append('thesis_title_continuation'); evidence.append('lowercase_thesis_degree_metadata')
    if DATE_ONLY_RX.match(text):
        # Date-only can be inherited-author or wrapped-author continuation.
        # A long author list on the immediately preceding line favors the latter.
        author_tokens = len(re.findall(r"(?:\b[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ'’\-]+\b|\b[A-Z]\.)", prev))
        separators = len(re.findall(r"[,;&]|\band\b|\by\b|\be\b", prev, re.I))
        if author_tokens >= 4 and separators >= 2:
            roles.append('wrapped_author_date'); evidence.append('date_only_after_long_author_list')
    # Title/source continuation: deliberately conservative.  Require an
    # explicit trailing connector or source noun, not merely capitalization.
    if index > 0 and not YEAR_ANY_RX.match(text):
        if re.search(r"\b(?:revista|journal|facultad|faculty)\b", text, re.I) or re.search(r"\b(?:de|of|and|y|e)\s*$", text, re.I):
            if not re.search(r"^[^,]{1,70},\s*[A-Z]", text):
                roles.append('title_or_source'); evidence.append('title_source_line_without_author_morphology')

    # Parenthetical acronym followed by access metadata is normally a second
    # physical line of an institutional reference.
    if re.match(r"^\([A-ZÁÉÍÓÚ0-9.\-]{2,20}\)\s*", text) and ACCESS_RX.search(text):
        roles.append('institution_access'); evidence.append('parenthetical_acronym_plus_access')

    # Strong conventional starts can contain words that also describe their
    # *body* (Journal, Available, etc.).  Protection is activated only when a
    # continuation role was actually found, so it never acts as a generic bonus
    # for unrelated weak candidates.  A wrapped author continuation remains
    # unprotected when the preceding physical line is an incomplete author list.
    if roles and not start_protected:
        late_tail = 'late_source_tail' in roles
        # A late source tail has priority over legacy weak start detectors.  It may
        # be overridden only by the stronger v0.8.7 person/title morphology or an
        # independent title-led reference.
        if not late_tail and late_author_title_start(index, lines):
            start_protected=True; start_kind='late_author_title'; evidence.append('strong_author_title_late_date_overrides_continuation_role')
        elif not late_tail and title_led_reference_start(index, lines):
            start_protected=True; start_kind='title_led_reference'; evidence.append('independent_title_led_reference_overrides_continuation_role')
        elif not late_tail and author_title_start(index, lines):
            start_protected=True; start_kind='person_author_title'; evidence.append('person_author_title_overrides_continuation_role')
        elif not late_tail and compact_person_author_year_start(text) and not _previous_is_incomplete_author_list(prev):
            start_protected=True; start_kind='compact_person_author'; evidence.append('compact_person_author_overrides_continuation_role')
        elif not late_tail and strong_person_author_date(text) and not _previous_is_incomplete_author_list(prev):
            start_protected=True; start_kind='person_author'; evidence.append('strong_person_author_overrides_continuation_role')
        elif not late_tail and dot_initial_author_date(text) and not _previous_is_incomplete_author_list(prev):
            start_protected=True; start_kind='person_author'; evidence.append('dot_initial_author_overrides_continuation_role')
        elif not late_tail and institutional_author_date(text):
            conference_linked = bool('conference_source' in roles and re.search(r'\b(?:in|en|em)\s*$', prev, re.I))
            if not conference_linked:
                start_protected=True; start_kind='institutional_author'; evidence.append('institutional_author_overrides_continuation_role')

    roles=list(dict.fromkeys(roles)); evidence=list(dict.fromkeys(evidence))
    return {
        'is_continuation': bool(roles) and not start_protected,
        'roles': roles,
        'evidence': evidence,
        'start_protected': start_protected,
        'start_kind': start_kind,
        'diagnostic_only': True,
    }

__all__=['classify_continuation_role']
