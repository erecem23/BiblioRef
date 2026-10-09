from __future__ import annotations

"""Title-reading v2.4: keep cover titles apart from labels, people and body text.

v2.3 still picked body sentences, acknowledgements and licence notes when the
cover title was split by a barrier, and it glued a personal name, a degree
statement or an institutional header to the real title. This revision keeps
the v2.1 geometry and scores and the v2.3 people barrier, and adds:

* explicit title labels ("TÍTULO:", "Título de la tesis:") as the strongest
  evidence, with the label stripped from the result;
* fragments are penalised: a candidate that starts in lower case, starts or
  ends on a dangling particle ("de", "en la"), or comes from a dense body page;
* a personal name set on its own line is not joined to a title line in a
  different case or type size, and name-only line groups (jury lists) lose;
* more degree/role/licence vocabulary acts as a barrier ("Tesis para acceder
  al grado de", "Doctoranda", "© 2024 ... licencia");
* a wrapped title may continue onto a line with an institutional word when
  the previous line ends on a particle ("... EN LA" / "UNIVERSIDAD: ...");
* a final clean-up strips leftover labels, quotes, trailing degree
  statements, role captions and known people from the chosen title.
"""
from pathlib import Path
from statistics import median
from typing import Iterable
import math
import re
import unicodedata

from . import document_title_v23 as _v23
from . import document_title as _base
from .metadata.cover_v05 import NAME_SUFFIX_EXCEPTIONS

TITLE_READING_REVISION = "document-title-v2.4"
title_conflicts_with_people = _v23.title_conflicts_with_people

DEGREE_TERMS = tuple(dict.fromkeys((
    *_base.DEGREE_TERMS,
    "tesis para acceder", "para acceder al grado", "para acceder al título", "para acceder al titulo",
    "para alcanzar el grado", "tesis para alcanzar", "grado de doctor", "grado de doctora",
    "grado académico de", "grado academico de", "título de doctor", "titulo de doctor",
    "título de doctora", "titulo de doctora", "título de magíster", "título de magister", "titulo de magister",
    "requisito parcial", "tesis presentada", "tesis de post grado", "tesis de posgrado", "tesis de postgrado",
    "trabajo integrador final", "trabajo final integrador", "carrera de especialización",
    "carrera de especializacion", "especialización en", "especializacion en", "tesis de maestría",
    "tesis de maestria", "tesis de licenciatura", "tesina", "doctorado en", "maestría en", "maestria en",
    "doctor en", "doctora en", "magíster en", "magister en",
)))
ROLE_TERMS = tuple(dict.fromkeys((
    *_base.ROLE_TERMS,
    "estudiante:", "alumna:", "alumno:", "especializanda:", "especializando:", "maestranda:", "maestrando:",
    "doctoranda:", "doctorando:", "doctoranda", "doctorando", "postulante:", "tesista:", "tutora:",
    "cotutora", "cotutor", "co-tutora", "co-tutor", "profesora guía", "profesor guía", "profesoras guía",
    "profesores guía", "co-guía", "directores:", "dirección:", "director de tesis", "directora de tesis",
    "codirectora", "co-directora", "codirector:",
)))
INST_TERMS = tuple(dict.fromkeys((
    *_base.INST_TERMS,
    "consejo nacional de investigaciones", "conicet", "laboratorio de", "repositorio institucional",
    "secretaría de ciencia", "secretaria de ciencia", "centro de investigación", "centro de investigaciones",
)))

_LICENSE_RE = re.compile(
    r"©|\bcreative\s+commons\b|\blicencia\b|\blicensed\b|\blicense\b|\bcc\s+by\b|\besta\s+obra\s+est[aá]\b|"
    r"\bthis\s+work\s+is\b|\brepositorio\b|\brepository\b|\bderechos\s+reservados\b|\ball\s+rights\s+reserved\b",
    re.I,
)
_TITLE_LABEL_RE = re.compile(
    r"^\s*t[ií]tulo(?:\s+(?:de(?:l)?\s+(?:la\s+)?)?(?:tesis|trabajo|obra|proyecto|tesina))?"
    r"\s*(?::|[.–—-]\s|(?=\s*[“\"«]))\s*",
    re.I,
)
_FIELD_LABEL_RE = re.compile(
    r"^(?:carrera|programa|fecha|imagen|im[aá]genes|lugar(?:\s+de\s+trabajo)?|tipo\s+de\s+licencia|licencia|"
    r"matr[ií]cula|dni|legajo|e-?mail|correo(?:\s+electr[oó]nico)?|cohorte|a[ñn]o|ciudad|sede|[aá]rea|"
    r"l[ií]nea\s+de\s+investigaci[oó]n|palabras\s+clave|keywords|estudiante|alumn[oa]|especializand[oa]|"
    r"maestrand[oa]|doctorand[oa]|postulante|tesista|co-?tutor(?:a)?|tutor(?:a)?|co-?director(?:a)?|"
    r"director(?:a)?(?:\s+de\s+tesis)?|autor(?:a)?|jurado|tribunal(?:\s+evaluador)?|evaluador(?:a|es)?|"
    r"co-?asesor(?:a)?|asesor(?:a)?|consejer[oa])\s*:",
    re.I,
)
_ROLE_CAPTION_RE = re.compile(
    r"^(?:autor(?:a)?|tesista|doctorand[oa]|maestrand[oa]|especializand[oa]|estudiante|alumn[oa]|postulante|"
    r"co-?director(?:a)?|director(?:a|es)?|co-?tutor(?:a)?|tutor(?:a)?|jurado|tribunal(?:\s+evaluador)?|"
    r"evaluador(?:a|es)?)$",
    re.I,
)
_HONORIFIC_START_RE = re.compile(r"^(?:esp|mg|mgt|mgter|mgtr|mgs|psic|magister|mag[ií]ster)\.?\s+", re.I)
_PERSON_PREFIX_RE = re.compile(
    r"^(?:(?:lic|licda|mg|mgt|mgter|mgtr|mgs|msc|dr|dra|prof|profesor|profesora|esp|psic|mr|mrs|ms|ph\.?d)\.?\s+)+",
    re.I,
)
_GENERIC_DOC_RE = re.compile(
    r"^(?:(?:las?|los)\s+)?(?:tesis|thesis|tesina|trabajo\s+(?:final|integrador)(?:\s+(?:final|integrador))?)"
    r"(?:\s+(?:doctoral|de\s+doctorado|de\s+maestr[ií]a|de\s+licenciatura))?$",
    re.I,
)
_HEADING_RE = re.compile(
    r"^(?:[íi]ndices?(?:\s+(?:general|de\s+\w+))?|tabla\s+de\s+contenidos?|agradecimientos?|dedicatoria|"
    r"resumen|abstract|palabras\s+clave|keywords|ep[íi]grafe)\s*:?$",
    re.I,
)
_DANGLING_END = {
    "de", "del", "la", "las", "los", "el", "en", "y", "e", "o", "u", "a", "al", "para", "por", "con", "sin",
    "sobre", "entre", "desde", "hacia", "ante", "tras", "que", "su", "sus", "of", "the", "and", "in", "for",
    "on", "to", "with",
}
_DANGLING_START = {"de", "del", "y", "e", "o", "u", "al", "que", "of", "and"}
# Words that occur in title lines but never inside a personal name, and noun
# endings typical of ALL-CAPS title lines ("EXPLICACIONES PSICOPATOLÓGICAS").
_NON_NAME_WORDS = {
    "en", "el", "con", "por", "para", "al", "su", "sus", "sobre", "entre", "a", "que", "o", "u", "un",
    "una", "unos", "unas", "sin", "desde", "hacia", "ante", "tras", "como", "mediante", "of", "the",
    "and", "in", "on", "for", "to", "with",
}
_NAME_EDGE_PARTICLES = {"de", "del", "la", "las", "los", "y", "e"}
_NOUN_SUFFIXES = (
    "cion", "ciones", "sion", "siones", "dad", "dades", "ismo", "ismos", "icas", "icos", "mente",
    "ivas", "ivos", "encia", "encias", "ancia", "ancias", "logia", "logias", "grafia",
)
_NUMBERED_RE = re.compile(
    r"^(?:\d+(?:\.\d+)*\.?\s|(?:parte|cap[ií]tulo|tabla|figura|gr[aá]fico|anexo|ap[eé]ndice|secci[oó]n)\s+"
    r"(?:\d+|[ivxlc]+)\b)",
    re.I,
)
_ACK_RE = re.compile(
    r"\b(?:agradec\w*|gracias|dedic(?:o|ada|ado)|financiad[oa]s?|financiaci[oó]n|financiamiento|subsidios?|"
    r"becas?|becari[oa]s?|convocatoria|solidaria|autor[ií]a\s+intelectual|compañer[oa]\s+de\s+vida|"
    r"mis\s+padres|mi\s+(?:madre|padre|mam[aá]|pap[aá]|familia|hij[oa]s?))\b|^a\s+(?:mis?|todos|todas)\s",
    re.I,
)
_LEADER_RE = re.compile(r"[.…]{4,}|…{2,}|https?://|www\.")


def _fold(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _has(text: str, terms) -> int:
    return _base.has_term(text, terms)


def _is_upper(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    return len(letters) >= 3 and sum(c.isupper() for c in letters) / len(letters) >= 0.85


def _ends_dangling(text: str) -> bool:
    ws = _base.words(text)
    return bool(ws) and _fold(ws[-1]) in _DANGLING_END


def _starts_lowercase(text: str) -> bool:
    first = next((c for c in text if c.isalpha()), "")
    return bool(first) and first.islower()


def _strip_honorifics(text: str) -> str:
    return _PERSON_PREFIX_RE.sub("", re.sub(r"^[^\w¿¡(“\"]+", "", _base.clean(text)))


def _likely_person(text: str) -> bool:
    """Stricter than likely_person_name: ALL-CAPS title lines are not names."""
    t = _strip_honorifics(text)
    if any(ch.isdigit() for ch in t) or not _base.likely_person_name(t):
        return False
    ws = [_fold(w) for w in _base.words(t)]
    if not ws or ws[0] in _NAME_EDGE_PARTICLES or ws[-1] in _NAME_EDGE_PARTICLES:
        return False
    # "A." / "E." are initials, not the words "a" / "e".
    tokens = [tok for tok in t.split() if not tok.endswith(".")]
    if any(_fold(tok.strip(",;:()\"“”")) in _NON_NAME_WORDS for tok in tokens):
        return False
    return not any(
        len(w) > 5 and w.endswith(_NOUN_SUFFIXES) and w not in NAME_SUFFIX_EXCEPTIONS for w in ws
    )


_BYLINE_RE = re.compile(r"^(?:por|by)\s+", re.I)
_INST_TYPO_RE = re.compile(r"\buniv\w{0,4}sidad\b|\bfacul\w{0,3}tad\b")


def _inst(text: str) -> int:
    """Institutional terms, tolerating typos such as "UNIVERISIDAD"."""
    return _has(text, INST_TERMS) or (1 if _INST_TYPO_RE.search(_fold(text)) else 0)


def _is_role_line(text: str) -> bool:
    t = _base.clean(text)
    byline = _BYLINE_RE.match(t)
    return bool(
        _base.is_role_line(t) or _has(t, ROLE_TERMS) or _FIELD_LABEL_RE.match(t)
        or _ROLE_CAPTION_RE.match(t) or _HONORIFIC_START_RE.match(t)
        or (byline and _base.likely_person_name(_strip_honorifics(t[byline.end():])))
    )


def _barrier(ln, prev=None, nxt=None, people=(), ignore_inst=False) -> bool:
    t = _base.clean(ln.text)
    if not t or _base.is_page_number(t):
        return True
    if _is_role_line(t):
        return True
    if t.casefold() in _base.GENERIC or _GENERIC_DOC_RE.match(t) or _HEADING_RE.match(t):
        return True
    if not ignore_inst and _inst(t) and len(_base.words(t)) <= 10:
        return True
    if _has(t, DEGREE_TERMS) and len(_base.words(t)) <= 15:
        return True
    if t.casefold() in _base.PAGE_ROLE_HEADINGS:
        return True
    if _LICENSE_RE.search(t) or _LEADER_RE.search(t):
        return True
    if people and title_conflicts_with_people(t, people):
        return True
    if _likely_person(t):
        if nxt and (_has(nxt.text, DEGREE_TERMS) or _inst(nxt.text) or _is_role_line(nxt.text)):
            return True
        if prev and prev.size >= ln.size * 1.15 and prev.yr < 0.65:
            return True
    return False


def _can_join(prev, cur, people=(), prev_soft=False) -> tuple[bool, bool]:
    """Return (joinable, joined_through_institutional_word)."""
    if _base.is_year_line(cur.text):
        return _base.can_join(prev, cur), False
    person_prev, person_cur = _likely_person(prev.text), _likely_person(cur.text)
    if person_prev != person_cur:
        person, other = (prev, cur) if person_prev else (cur, prev)
        ratio = min(prev.size, cur.size) / max(prev.size, cur.size, 1)
        different = _is_upper(person.text) != _is_upper(other.text) or ratio < 0.94
        if different and not (person_cur and _ends_dangling(prev.text)):
            return False, False
    soft = False
    if _barrier(cur, prev, None, people):
        # "... EN LA" / "UNIVERSIDAD: NUEVOS RECURSOS ..." is one wrapped title.
        if not (_ends_dangling(prev.text) and not _barrier(cur, prev, None, people, ignore_inst=True)):
            return False, False
        soft = True
    if _barrier(prev, None, cur, people, ignore_inst=prev_soft):
        return False, False
    gap = cur.y0 - prev.y1
    mx = max(prev.size, cur.size, 1)
    if gap < -max(5.0, 0.45 * mx) or gap > max(32, 2.35 * mx):
        return False, False
    ratio = min(prev.size, cur.size) / max(prev.size, cur.size)
    if ratio < 0.56:
        tight = gap <= 1.15 * min(prev.size, cur.size)
        aligned = abs(prev.center - cur.center) <= 0.09 or abs(prev.x0 - cur.x0) <= 0.06 * prev.width
        if ratio < 0.42 or not (tight and aligned):
            return False, False
    if abs(prev.center - cur.center) > 0.30 and abs(prev.x0 - cur.x0) > 0.20 * prev.width:
        return False, False
    return True, soft


def _dense_body(lines) -> bool:
    texts = [_base.clean(x.text) for x in lines if _base.clean(x.text) and not _base.is_page_number(x.text)]
    if len(texts) < 20:
        return False
    return sum(1 for t in texts if len(_base.words(t)) >= 8) >= 0.6 * len(texts)


def _page_penalty(lines) -> float:
    """Dense body pages and tables of contents do not carry the thesis title."""
    if _dense_body(lines):
        return 22.0
    if _base.page_role(lines) is None:
        entries = sum(
            1 for x in lines
            if _NUMBERED_RE.match(_base.clean(x.text)) or re.search(r"(?:[.…]{2,}|\s)\s*\d{1,3}$", x.text)
        )
        if entries >= 8:
            return 18.0
    return 0.0


def _title_page_signal(lines) -> float:
    joined = " ".join(x.text for x in lines)
    signal = 0.0
    if _has(joined, DEGREE_TERMS):
        signal += 5
    if _inst(joined):
        signal += 2
    if _has(joined, ROLE_TERMS):
        signal += 2
    if len(lines) <= 18:
        signal += 2
    role = _base.page_role(lines)
    if role == "repository-coversheet":
        signal -= 14
    elif role:
        signal -= 4
    return signal


def _starts_with_inst(text: str) -> bool:
    low = _fold(_base.clean(text))
    return any(low.startswith(_fold(term)) for term in INST_TERMS)


def _candidate_score(group, role, signal, page_penalty, people) -> float:
    text = _base.clean(" ".join(x.text for x in group))
    if not _base.plausible(text):
        return -math.inf
    ws = _base.words(text)
    size = median([x.size for x in group])
    med = max(1, median([x.med for x in group]))
    prominence = size / med
    page = group[0].page
    yr = sum(x.yr for x in group) / len(group)
    score = 13 + max(-4, min(24, (prominence - 1) * 20)) + min(len(text), 220) / 32
    if 4 <= len(ws) <= 35:
        score += 5
    if 2 <= len(group) <= 4:
        score += 4
    if len(group) >= 2:
        cont = 0
        for ln in group[1:]:
            t = _base.clean(ln.text)
            if _base.is_year_line(t) or (t and t[0].islower()):
                cont += 1
        score += min(6.0, 4.0 * cont)
    if 0.14 <= yr <= 0.68:
        score += 6
    elif 0.06 <= yr <= 0.80:
        score += 2
    else:
        score -= 5
    centers = [x.center for x in group]
    lefts = [x.x0 / x.width for x in group]
    if max(centers) - min(centers) <= 0.11 or max(lefts) - min(lefts) <= 0.07:
        score += 3
    if abs(sum(centers) / len(centers) - 0.5) <= 0.14:
        score += 2
    score += signal
    inst = _inst(text)
    roles = _has(text, ROLE_TERMS)
    degree = _has(text, DEGREE_TERMS)
    # An institutional word inside a long wrapped title ("... en la Escuela de
    # Medicina de la UNMdP ...") is weaker evidence than a header line.
    inst_penalty = 4 if len(ws) >= 10 and not any(_starts_with_inst(x.text) for x in group) else 16
    score -= inst_penalty * inst + 20 * roles
    if degree and len(ws) <= 16:
        score -= 12 * degree
    if _base.looks_path(text):
        score -= 25
    if _LICENSE_RE.search(text):
        score -= 30
    if role == "repository-coversheet":
        score -= 55
    elif role:
        top = max(x.yr for x in group) <= 0.10
        score += 4 if top else -18
    score -= page_penalty
    score -= page * 1.8
    # Table-of-contents entries, acknowledgements and funding notes.
    if _NUMBERED_RE.match(text):
        score -= 20
    score -= min(40, 14 * len(_ACK_RE.findall(text)))
    # Fragments of a longer text.
    if _starts_lowercase(text):
        score -= 25
    if _fold(ws[0]) in _DANGLING_START:
        score -= 12
    if _fold(ws[-1]) in _DANGLING_END:
        score -= 12
    # People: jury/name lists and names glued to the first or last title line.
    persons = [_likely_person(x.text) for x in group]
    if len(group) >= 2 and all(persons):
        score -= 15 if all(_is_upper(x.text) for x in group) else 40
    elif len(group) >= 2:
        if persons[0] and not persons[1]:
            score -= 16
        if persons[-1] and not persons[-2] and not _ends_dangling(group[-2].text):
            score -= 16
    elif persons[0] and len(ws) <= 5:
        score -= 10
    if people and any(title_conflicts_with_people(x.text, people) for x in group):
        score -= 30
    return score


def _layout_candidates(pdf, people=(), max_pages: int = 6):
    page_lines, roles, signals, dense = [], [], [], []
    for pno in range(min(max_pages, len(pdf))):
        lines = _base.extract_lines(pdf[pno], pno)
        page_lines.append(lines)
        roles.append(_base.page_role(lines))
        signals.append(_title_page_signal(lines))
        dense.append(_page_penalty(lines))
    out = []
    for pno, lines in enumerate(page_lines):
        if roles[pno] == "repository-coversheet":
            continue
        n = len(lines)
        for i, ln in enumerate(lines):
            prev = lines[i - 1] if i else None
            nxt = lines[i + 1] if i + 1 < n else None
            if _barrier(ln, prev, nxt, people) or _base.is_year_line(ln.text):
                continue
            group = [ln]
            score = _candidate_score(group, roles[pno], signals[pno], dense[pno], people)
            if math.isfinite(score):
                out.append(_base.Candidate(_base.clean(ln.text), score, "cover_layout", pno, i, i))
            soft = False
            for j in range(i + 1, min(n, i + 6)):
                ok, soft = _can_join(group[-1], lines[j], people, prev_soft=soft)
                if not ok:
                    break
                group.append(lines[j])
                score = _candidate_score(group, roles[pno], signals[pno], dense[pno], people)
                if math.isfinite(score):
                    text = _base.clean(" ".join(x.text for x in group))
                    out.append(_base.Candidate(text, score, "cover_layout", pno, i, j))
    # Running headers that repeat the title near the top of later pages.
    repeat_pool = []
    for cand in out:
        if cand.page < 0 or len(cand.text) > 220:
            continue
        lines = page_lines[cand.page]
        if cand.start < len(lines) and lines[cand.start].yr <= 0.115:
            repeat_pool.append(cand)
    boosted = []
    for cand in out:
        bonus = 0.0
        if cand in repeat_pool:
            reps = {o.page for o in repeat_pool if o.page != cand.page and _base.similarity(cand.text, o.text) >= 0.86}
            if reps:
                bonus = min(18.0, 6.0 * len(reps)) + 8.0
        boosted.append(_base.Candidate(cand.text, cand.score + bonus, cand.source, cand.page, cand.start, cand.end))
    return boosted


def _strip_quotes(text: str) -> str:
    t = _base.norm(text)
    t = re.sub(r"^[“\"«'‘]+\s*", "", t)
    t = re.sub(r"\s*[”\"»'’]+$", "", t)
    if t.count("“") != t.count("”"):
        t = t.replace("“", "").replace("”", "")
    return _base.norm(t)


def _labeled_candidates(pdf, max_pages: int = 6):
    """Titles introduced by an explicit label ("TÍTULO:", "Título de la tesis:")."""
    out = []
    for pno in range(min(max_pages, len(pdf))):
        lines = _base.extract_lines(pdf[pno], pno)
        for i, ln in enumerate(lines):
            match = _TITLE_LABEL_RE.match(ln.text)
            if not match:
                continue
            parts = [ln.text[match.end():]]
            last = ln
            for nxt in lines[i + 1:i + 6]:
                t = _base.clean(nxt.text)
                if not t:
                    break
                gap = nxt.y0 - last.y1
                mx = max(last.size, nxt.size, 1)
                if gap > max(12.0, 1.9 * mx) or gap < -max(5.0, 0.45 * mx):
                    break
                if min(last.size, nxt.size) / mx < 0.8:
                    break
                if _FIELD_LABEL_RE.match(t) or _TITLE_LABEL_RE.match(t) or _is_role_line(t) or _LICENSE_RE.search(t):
                    break
                header = _has(t, DEGREE_TERMS) or (_inst(t) and len(_base.words(t)) <= 10)
                if header and not _ends_dangling(" ".join(parts)):
                    break
                parts.append(nxt.text)
                last = nxt
            text = _strip_quotes(_base.clean(" ".join(parts)))
            if _base.plausible(text) and len(_base.words(text)) >= 3:
                out.append(_base.Candidate(text, 72.0 - 2.0 * pno, "cover_layout", pno, i, i + len(parts) - 1))
    return out


def _role_linked_people(pdf, max_pages: int = 6) -> list[str]:
    """Names attached to author/advisor/jury labels, including whole jury lists."""
    found: list[str] = []
    for pno in range(min(max_pages, len(pdf))):
        lines = _base.extract_lines(pdf[pno], pno)
        for i, line in enumerate(lines):
            text = _base.clean(line.text)
            inline = _v23._inline_role_person(text)
            if inline:
                found.append(inline)
                continue
            if not (_v23._ROLE_PREFIX_RE.match(text) or _ROLE_CAPTION_RE.match(text)):
                continue
            anchor = line
            for nxt in lines[i + 1:i + 8]:
                t = _base.clean(nxt.text)
                if not t:
                    continue
                if _v23._ROLE_PREFIX_RE.match(t) or _inst(t) or _has(t, DEGREE_TERMS):
                    break
                if nxt.y0 - anchor.y1 > max(42.0, 3.0 * max(anchor.size, nxt.size, 1.0)):
                    break
                name = _strip_honorifics(t)
                if not _base.likely_person_name(name):
                    break
                found.append(name)
                anchor = nxt
    out: list[str] = []
    seen: set[tuple[str, ...]] = set()
    for value in found:
        key = _v23._name_tokens(value)
        if key and key not in seen:
            seen.add(key)
            out.append(value)
    return out


def _cased(*words: str) -> str:
    """Alternation of words in Title case and UPPER case (role words in titles stay)."""
    return "(?:" + "|".join(v for w in words for v in (w, w.upper())) + ")"


_TAIL_CUTS = (
    re.compile(r"\s+(?:" + _cased("Tesis") + r"\s+(?:para|presentada|de\s+(?:doctorado|maestr[ií]a|licenciatura|post\s*grado|posgrado)|doctoral)"
               r"|(?:para|PARA)\s+(?:optar|obtener|acceder|alcanzar|OPTAR|OBTENER|ACCEDER|ALCANZAR)\b"
               r"|" + _cased("Trabajo") + r"\s+(?:final|integrador|FINAL|INTEGRADOR)).*$", re.I),
    re.compile(r"\s+" + _cased("Índice", "Indice") + r"(?:\s+(?:general|GENERAL))?\s*$"),
    re.compile(r"\s*[”\"»]?\s+" + _cased("Doctoranda", "Doctorando", "Autora", "Autor", "Tesista", "Estudiante",
                                         "Alumna", "Alumno", "Postulante", "Directora", "Director",
                                         "Codirectora", "Codirector") + r"\b.*$"),
    re.compile(r"\s*[”\"»]?\s+(?:(?:Esp|Lic|Dr|Dra|Mg|Mgter|Mgt|Prof|Psic)\.\s*)+[A-ZÁÉÍÓÚÑ].*$"),
    re.compile(r"\s+(?:CONSEJO|Consejo)\s+(?:NACIONAL|Nacional)\s+(?:DE|de)\s+(?:INVESTIGACIONES|Investigaciones)\b.*$"),
    # A byline started on the title's last line ("... GESTANTES por").
    re.compile(r"\s+(?:por|POR|Por|by|BY|By)\s*$"),
)
_DOC_TYPE_PREFIX_RE = re.compile(
    r"^(?:tesis\s+(?:doctoral|de\s+doctorado|de\s+maestr[ií]a|de\s+licenciatura)|tesis|thesis)\s*[:.\-–—]?\s+",
    re.I,
)


def _strip_people(text: str, people: Iterable[str]) -> str:
    keys = [set(_v23._name_tokens(p)) for p in people]
    keys = [k for k in keys if len(k) >= 2]
    toks = text.split()
    changed = bool(keys)
    while changed and len(toks) > 4:
        changed = False
        for n in range(min(6, len(toks) - 3), 1, -1):
            if set(_v23._name_tokens(" ".join(toks[:n]))) in keys:
                toks, changed = toks[n:], True
                break
            if set(_v23._name_tokens(" ".join(toks[-n:]))) in keys:
                toks, changed = toks[:-n], True
                break
    return " ".join(toks)


def clean_title(text: str, people: Iterable[str] = ()) -> str:
    """Remove labels, quotes and front-matter leftovers from a chosen title."""
    t = _base.norm(text)
    t = _TITLE_LABEL_RE.sub("", t, count=1)
    t = re.split(r"\s+\|\s+|\s+[·•]\s+", t)[0]
    prefix = _DOC_TYPE_PREFIX_RE.match(t)
    if prefix and len(_base.words(t[prefix.end():])) >= 3:
        t = t[prefix.end():]
    t = _strip_people(t, people)
    for cut in _TAIL_CUTS:
        match = cut.search(t)
        if match and len(_base.words(t[:match.start()])) >= 4:
            t = t[:match.start()]
    t = _strip_people(t, people)
    t = _strip_quotes(t)
    return _base.clean(t)


def _metadata_garbage(text: str) -> bool:
    low = _fold(text)
    if not low or text.lstrip().startswith("("):
        return True
    if any(x in low for x in ("scanned", "escaneado", "epigrafe")):
        return True
    ws = _base.words(text)
    return len(ws) <= 3 and any(_fold(w) in {"tesis", "thesis", "tesina"} for w in ws)


def _metadata_candidate(pdf, fallback: str, people, ranked):
    meta = _base.clean((pdf.metadata or {}).get("title") or "")
    meta = re.split(r"\s+\|\s+", meta)[0]
    prefix = _DOC_TYPE_PREFIX_RE.match(meta)
    if prefix and len(_base.words(meta[prefix.end():])) >= 3:
        meta = meta[prefix.end():]
    meta = _base.clean(meta)
    if _metadata_garbage(meta):
        return None
    if _starts_lowercase(meta[:1]):
        meta = meta[:1].upper() + meta[1:]
    score = _base.metadata_score(meta, fallback)
    if not math.isfinite(score) or title_conflicts_with_people(meta, people):
        return None
    overlap = max((_base.similarity(meta, c.text) for c in ranked), default=0)
    if overlap >= 0.72:
        score += 20
    page_cover = 0.0
    for pno in range(min(3, len(pdf))):
        lines = _base.extract_lines(pdf[pno], pno)
        if _base.page_role(lines) == "repository-coversheet":
            continue
        evidence = " ".join(x.text for x in lines if x.yr <= 0.68)
        page_cover = max(page_cover, _base._token_coverage(meta, evidence))
    if page_cover >= 0.90:
        score += 34
    elif page_cover >= 0.75:
        score += 22
    return _base.Candidate(meta, score, "pdf_metadata", -1)


def detect_thesis_title(
    path: Path,
    filename: str,
    *,
    excluded_people: Iterable[str] = (),
) -> tuple[str, str]:
    """Detect a thesis title from the cover/front matter, falling back to the filename."""
    path = Path(path)
    filename = str(filename)
    fallback = _base.filename_as_title(filename)
    if _base.fitz is None:
        return fallback, "filename"
    try:
        with _base.fitz.open(path) as pdf:
            people = [str(x) for x in excluded_people if str(x or "").strip()]
            people.extend(_role_linked_people(pdf))
            meta_author = _base.clean((pdf.metadata or {}).get("author") or "")
            if _base.likely_person_name(meta_author):
                people.append(meta_author)

            ranked = [
                cand for cand in _layout_candidates(pdf, people)
                if not title_conflicts_with_people(cand.text, people)
            ]
            ranked.extend(_labeled_candidates(pdf))
            meta = _metadata_candidate(pdf, fallback, people, ranked)
            if meta is not None:
                ranked.append(meta)

            ranked.sort(key=lambda c: (c.score, len(c.text)), reverse=True)
            for cand in ranked:
                if cand.score < 24:
                    break
                text = clean_title(cand.text, people)
                if not _base.plausible(text) or _starts_lowercase(text):
                    continue
                if title_conflicts_with_people(text, people):
                    continue
                return text, cand.source
    except Exception:
        pass
    return fallback, "filename"


__all__ = [
    "TITLE_READING_REVISION",
    "clean_title",
    "detect_thesis_title",
    "title_conflicts_with_people",
]
