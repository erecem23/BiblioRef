# -*- coding: utf-8 -*-
from __future__ import annotations

"""Front-matter metadata v0.5.

v0.4 widened the scan to eight front-matter pages, which also let
acknowledgements, abstracts, licence notes and body text leak into the
metadata ("Universidad Nacional de Córdoba, por todas las enseñanzas",
"centro de la intervención", "Imagen: Carolina Monterrubio"). v0.5 keeps the
v0.4 reading but re-derives every field from front-matter pages only and
validates each value:

* pages headed by acknowledgements/abstract/index/etc. and dense body pages
  are not read;
* people lose role labels and honorifics ("ESTUDIANTE:", "Doctor.
  Especialista,", "Esp. Lic.", "(UNLP)") and are rejected when what is left
  is not a personal name; a caption placed under the name ("Directora") is
  read as well as one placed above it;
* affiliations are proper-noun runs that start a line or a " – " segment and
  may continue on the next line ("UNIVERSIDAD NACIONAL DE" / "LA PLATA");
* years inside ranges such as "(1944-1953)" are ignored;
* degree level and program come from explicit degree statements.

Bibliography extraction and reference parsing remain untouched.
"""
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import cover as _base
from . import cover_v04 as _v04

COVER_METADATA_VERSION = "cover-metadata-v0.5.2"
_MAX_FRONTMATTER_PAGES = 8

Line = Dict[str, Any]


def _norm(value: Any) -> str:
    return _base._norm(value)


def _fold(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


_WORD_RE = re.compile(r"[^\W\d_]+(?:['’.\-][^\W\d_]+)*\.?")

# --------------------------------------------------------------------------
# Page selection
# --------------------------------------------------------------------------
_SECTION_HEADING_RE = re.compile(
    r"^(?:agradecimientos?|reconocimientos?|acknowledge?ments?|dedicatorias?|dedication|"
    r"ep[ií]grafe|resumen|abstract|resumo|r[eé]sum[eé]|palabras\s+clave|keywords|"
    r"[ií]ndices?(?:\s+general|\s+de\s+\w+)?|contenidos?|tabla\s+de\s+contenidos?|"
    r"table\s+of\s+contents|contents|introducci[oó]n(?:\s+general)?|introduction|"
    r"pr[oó]logo|prefacio|preface|fuentes\s+de\s+financiamiento|financiamiento|"
    r"eternamente\s+gracias|lista\s+de\s+(?:tablas|figuras|abreviaturas)|"
    r"cap[ií]tulo\s+\S+)$",
    re.I,
)


def _page_kind(lines: List[Line]) -> str:
    """Classify a page as cover/front matter or as a section that is not read."""
    texts = [_norm(ln["text"]) for ln in lines if _norm(ln["text"])]
    if not texts:
        return "empty"
    for ln in lines[:3]:
        if float(ln["y0"]) > 0.35 * float(ln.get("height") or 1):
            break
        head = _norm(ln["text"]).strip(" .:;-–—¡!¿?\"“”'")
        if _SECTION_HEADING_RE.match(head):
            return "section"
    if sum(1 for t in texts if re.search(r"\.{4,}|…{3,}", t)) >= 4:
        return "contents"
    wordy = sum(1 for t in texts if len(t.split()) >= 8)
    if len(texts) >= 20 and wordy >= 0.6 * len(texts):
        return "body"
    return "front"


# --------------------------------------------------------------------------
# People
# --------------------------------------------------------------------------
_ROLE_END = r"(?![^\W\d_])\s*[:.\-–—]?\s*"
_AUTHOR_ROLE_RE = re.compile(
    r"^(?:autor(?:a|es|as)?(?:\s+de\s+(?:la\s+)?tesis)?|author|tesista|"
    r"(?:doctorand[oa]|maestrand[oa]|especializand[oa])(?:\s+en\s+[^\W\d_]+)?|doctorante|"
    r"estudiante|alumn[oa]|postulante|aspirante|candidat[oa]|candidate|"
    r"presentan?|(?:presentad[oa]|realizad[oa]|elaborad[oa])\s+por|presented\s+by|submitted\s+by|"
    r"written\s+by|por)" + _ROLE_END,
    re.I,
)
_DIRECTOR_RE = re.compile(
    r"^(?:director(?:a|as|es|xs)?(?:\s+de\s+(?:la\s+)?(?:tesis|tesina)|\s+del?\s+trabajo(?:\s+final)?(?:\s+integrador)?)?|"
    r"direcci[oó]n(?:\s+de\s+(?:la\s+)?tesis)?|dirigid[oa]\s+por|"
    r"thesis\s+(?:director|supervisor|advisor)|supervisor(?:a)?|advisor|adviser|"
    r"orientador(?:a)?|tutor(?:a)?(?:\s+de\s+(?:la\s+)?tesis)?|profesor(?:a|as|es)?\s+gu[ií]as?|"
    r"asesor(?:/a|a|as|es)?(?:\s+de\s+(?:la\s+)?tesis)?)" + _ROLE_END,
    re.I,
)
_CODIRECTOR_RE = re.compile(
    r"^(?:co-?\s?director(?:a|as|es|xs)?(?:\s+de\s+(?:la\s+)?tesis|\s+del?\s+trabajo(?:\s+final)?)?|"
    r"codirecci[oó]n|co-?supervisor(?:a)?|co-?advisor|co-?adviser|co-?orientador(?:a)?|"
    r"co-?tutor(?:a)?|profesor(?:a|as|es)?\s+co-?gu[ií]as?|co-?gu[ií]a|co-?asesor(?:/a|a|as|es)?)" + _ROLE_END,
    re.I,
)
_JURY_RE = re.compile(
    r"^(?:tribunal|jurado|comit[eé]|comisi[oó]n\s+(?:evaluadora|asesora)|miembros\s+del\s+(?:tribunal|jurado)|"
    r"evaluador(?:a|es|as)?|evaluation\s+committee|examining\s+committee|thesis\s+committee|"
    r"jury|examiners?|banca)(?![^\W\d_])",
    re.I,
)
_PERSON_ROLE_RES = (_AUTHOR_ROLE_RE, _DIRECTOR_RE, _CODIRECTOR_RE)
_ANY_LABEL_RE = re.compile(r"^([^\W\d_][^\W\d_.]*(?:[ \-][^\W\d_]+){0,3})\s*:\s*(.*)$")
_HONORIFIC_RE = re.compile(
    r"^(?:(?:dr|dra|dres|doctor|doctora|lic|lcdo|lcda|licdo|licda|licenciad[oa]|mg|mgs|mgt|mgter|mgtr|mgr|"
    r"mag|mag[ií]ster|msc|m\.\s?sc|esp|especialista|prof|profa|profesor|profesora|psic|psic[oó]log[oa]|"
    r"ab|abog|abogad[oa]|ing|arq|sr|sra|srta|ph\.?\s?d)[.,\s][\s.,]*)+",
    re.I,
)
_TRAILING_CREDENTIAL_RE = re.compile(r"[\s,]+(?:ph\.?\s?d\.?|m\.?\s?sc\.?|dr\.?|dra\.?)$", re.I)
_NAME_PARTICLES = {"de", "del", "la", "las", "los", "y", "e", "da", "do", "dos", "das", "van", "von", "der", "di", "du", "le"}
_NAME_EDGE_PARTICLES = {"de", "del", "la", "las", "los", "y", "e"}
_NON_NAME_WORDS = {
    "en", "el", "con", "por", "para", "al", "su", "sus", "sobre", "entre", "a", "que", "o", "u", "un",
    "una", "sin", "desde", "hacia", "como", "of", "the", "and", "in", "on", "for", "to", "with",
}
_NOUN_SUFFIXES = (
    "cion", "ciones", "sion", "siones", "dad", "dades", "ismo", "ismos", "icas", "icos", "mente",
    "ivas", "ivos", "encia", "encias", "ancia", "ancias", "logia", "logias", "grafia",
)
# Given names and surnames that happen to carry one of those noun endings.
NAME_SUFFIX_EXCEPTIONS = {
    "soledad", "piedad", "caridad", "trinidad", "natividad", "felicidad", "florencia", "valencia",
    "constancia", "clemencia", "prudencia", "inocencia", "placencia", "asuncion", "concepcion",
    "encarnacion", "purificacion", "anunciacion", "consolacion", "ascension", "visitacion",
}
_PERSON_STOP = {
    "universidad", "facultad", "instituto", "departamento", "escuela", "centro", "laboratorio", "consejo",
    "conicet", "doctor", "doctora", "doctorado", "doctorando", "doctoranda", "maestria", "magister",
    "maestrando", "maestranda", "especializacion", "especialista", "licenciatura", "tesis", "tesina",
    "psicologia", "ciencias", "humanidades", "director", "directora", "codirector", "codirectora", "tutor",
    "tutora", "beca", "argentina", "republica", "creative", "commons", "licencia", "microsoft", "cuenta",
    "usuario", "user", "admin", "administrador", "owner", "carrera", "programa", "jurado", "tribunal",
    "evaluador", "evaluadora", "imagen", "fecha", "titulo", "resumen", "abstract", "indice",
    "agradecimientos", "nacional", "provincia", "buenos", "aires", "plata", "ciudad", "trabajo",
    "integrador", "final", "presentacion", "presentada", "requisito", "grado", "repositorio",
}


def _is_person_role_label(label: str) -> bool:
    for role_re in _PERSON_ROLE_RES:
        match = role_re.match(label)
        if match and not label[match.end():].strip(" .:;,-–—"):
            return True
    return False


def _is_bare_role_label(text: str) -> bool:
    text = _norm(text)
    if _JURY_RE.match(text):
        return True
    return _is_person_role_label(text)


def _person_case(text: str) -> str:
    letters = [c for c in text if c.isalpha()]
    if not letters or sum(c.isupper() for c in letters) / len(letters) <= 0.85:
        return text
    out = []
    for i, word in enumerate(text.lower().split()):
        if i and word in _NAME_PARTICLES:
            out.append(word)
            continue
        word = re.sub(r"(^|-)([^\W\d_])", lambda m: m.group(1) + m.group(2).upper(), word)
        # D’ANGELO -> D’Angelo, but RICHARD’S -> Richard’s.
        word = re.sub(r"([’'])([^\W\d_])(?=[^\W\d_]{2})", lambda m: m.group(1) + m.group(2).upper(), word)
        out.append(word)
    return " ".join(out)


def _valid_person(text: str) -> bool:
    if not text or re.search(r"\d|@|https?:|www\.|[:;?!/\\|()]", text):
        return False
    words = _WORD_RE.findall(text)
    if not 2 <= len(words) <= 7:
        return False
    significant = [w for w in words if _fold(w) not in _NAME_PARTICLES]
    if not 2 <= len(significant) <= 6:
        return False
    folded = [_fold(w).strip(".") for w in words]
    if folded[0] in _NAME_EDGE_PARTICLES or folded[-1] in _NAME_EDGE_PARTICLES:
        return False
    # "A." / "E." are initials, not the words "a" / "e".
    if any(f in _NON_NAME_WORDS for f, w in zip(folded, words) if not w.endswith(".")):
        return False
    for word in significant:
        low = _fold(word.strip("."))
        if not word[:1].isupper() or low in _PERSON_STOP:
            return False
        if len(low) > 5 and low.endswith(_NOUN_SUFFIXES) and low not in NAME_SUFFIX_EXCEPTIONS:
            return False
    return True


def clean_person(value: Any) -> Optional[str]:
    """Return a bare personal name, or None when *value* is not one.

    Role labels ("ESTUDIANTE:"), connectors ("y", "Por"), honorifics and
    degree titles ("Doctor. Especialista,", "Esp. Lic.", "Mgter.") and
    trailing affiliations ("(UNLP)", "| UNLP") are removed first. A value with
    any other label ("Imagen: ...", "Lugar de trabajo: ...") is rejected.
    """
    text = _norm(re.sub(r"\S+@\S+", " ", str(value or "")))
    text = re.sub(r"^[^\w(¿¡]+", "", text)
    label = _ANY_LABEL_RE.match(text)
    if label:
        if not _is_person_role_label(label.group(1)):
            return None
        text = label.group(2)
    text = re.sub(r"\s*\([^)]*\)?", " ", text)
    # Keep the first person of "Name · Name", "Name & Name", "Name y Dr. Name"
    # and drop trailing affiliations such as "| UNLP".
    text = re.split(
        r"\s+[|–—·•&]\s*|\s*[·•;&]\s+|\s+-\s+|\s+y\s+(?=(?:dr|dra|lic|prof|mg|mgter|esp)\.?\s)",
        text, maxsplit=1, flags=re.I,
    )[0]
    for _ in range(3):
        before = text
        text = _norm(text).strip(" .,;:-–—")
        text = re.sub(r"^(?:y|e|and|por|by|&)\s+", "", text, flags=re.I)
        text = _HONORIFIC_RE.sub("", text)
        text = _TRAILING_CREDENTIAL_RE.sub("", text)
        if text == before:
            break
    text = _norm(text).strip(" .,;:-–—")
    if not _valid_person(text):
        return None
    return _person_case(text)


def _name_key(value: str) -> frozenset:
    return frozenset(
        _fold(w).strip(".") for w in _WORD_RE.findall(value or "")
        if _fold(w) not in _NAME_PARTICLES and len(_fold(w).strip(".")) > 1
    )


def _near(upper: Line, lower: Line) -> bool:
    gap = float(lower["y0"]) - float(upper["y1"])
    size = max(float(upper.get("size") or 0), float(lower.get("size") or 0), 1.0)
    return gap <= max(48.0, 3.4 * size)


def _name_first_block(lines: List[Line], index: int) -> bool:
    """True when a name/caption block lists the name above its role caption."""
    start = kind_prev = "label"
    cur = lines[index]
    for k in range(index - 1, -1, -1):
        ln = lines[k]
        if not _near(ln, cur):
            break
        text = _norm(ln["text"])
        if _is_bare_role_label(text):
            kind = "label"
        elif clean_person(text):
            kind = "person"
        else:
            break
        if kind == kind_prev:
            break
        start = kind_prev = kind
        cur = ln
    return start == "person"


def _adjacent_person(lines: List[Line], index: int) -> Tuple[Optional[str], float]:
    person, conf, _ = _adjacent_person_at(lines, index)
    return person, conf


def _adjacent_person_at(lines: List[Line], index: int) -> Tuple[Optional[str], float, Optional[int]]:
    """Value of a bare role label and the index of the line it came from."""
    anchor = lines[index]
    below = None
    below_at = None
    for j in range(index + 1, min(len(lines), index + 4)):
        nxt = lines[j]
        text = _norm(nxt["text"])
        if not text:
            continue
        if _is_bare_role_label(text) or not _near(anchor, nxt):
            break
        below = clean_person(text)
        if below or len(text.split()) > 8:
            below_at = j
            break
    if not _norm(anchor["text"]).endswith(":") and index > 0:
        # Caption under the name ("Mgt. X" / "Doctoranda" / "Dra. Y" / "Directora"):
        # the name below belongs to the next caption, or there is none.
        next_is_caption = (
            below_at is not None and below_at + 1 < len(lines)
            and _near(lines[below_at], lines[below_at + 1])
            and _is_bare_role_label(_norm(lines[below_at + 1]["text"]))
        )
        prev = lines[index - 1]
        above = clean_person(prev["text"]) if _near(prev, anchor) else None
        if above and (not below or next_is_caption) and _name_first_block(lines, index):
            return above, 0.93, index - 1
    if below:
        return below, 0.96, below_at
    return None, 0.0, None


def _role_value(lines: List[Line], index: int, role_re: re.Pattern[str]) -> Tuple[Optional[str], float]:
    raw = _norm(lines[index]["text"])
    match = role_re.match(raw)
    if not match:
        return None, 0.0
    rest = raw[match.end():].strip(" .:;,-–—")
    if rest:
        person = clean_person(rest)
        return (person, 0.99) if person else (None, 0.0)
    return _adjacent_person(lines, index)


_PAREN_ROLE_RE = re.compile(
    r"^(?P<name>.+?)\s*\(\s*(?P<role>co-?\s?director(?:a)?|director(?:a)?|co-?tutor(?:a)?|tutor(?:a)?|autor(?:a)?)"
    r"\s*\)\s*$",
    re.I,
)


def _paren_role(text: str) -> Tuple[Optional[str], Optional[str]]:
    """"Dra. Karin Arbach (directora)" -> ("director", "Karin Arbach")."""
    match = _PAREN_ROLE_RE.match(text)
    if not match:
        return None, None
    role = re.sub(r"[\s-]", "", _fold(match.group("role")))
    key = "codirector" if role.startswith("co") else "author" if role.startswith("autor") else "director"
    return key, clean_person(match.group("name"))


def _detect_role_people(pages: List[List[Line]]):
    found: Dict[str, Tuple[Optional[str], float]] = {
        "author": (None, 0.0), "director": (None, 0.0), "codirector": (None, 0.0),
    }
    for lines in pages:
        for i, ln in enumerate(lines):
            text = _norm(ln["text"])
            key, person = _paren_role(text)
            if key:
                if person and found[key][0] is None:
                    found[key] = (person, 0.97)
                continue
            if found["codirector"][0] is None and _CODIRECTOR_RE.match(text):
                found["codirector"] = _role_value(lines, i, _CODIRECTOR_RE)
            elif found["director"][0] is None and _DIRECTOR_RE.match(text):
                found["director"] = _role_value(lines, i, _DIRECTOR_RE)
            elif found["author"][0] is None and _AUTHOR_ROLE_RE.match(text):
                found["author"] = _role_value(lines, i, _AUTHOR_ROLE_RE)
        if all(value for value, _ in found.values()):
            break
    return found


def _role_block_people(lines: List[Line]) -> Tuple[set, List[frozenset]]:
    """Lines (and name keys) that hold the value of a bare role label.

    A label followed by several names ("Directores:" / three names, a jury
    list) owns all of them, so none of them can pass for the author.
    """
    consumed: set = set()
    for i, ln in enumerate(lines):
        if not _is_bare_role_label(_norm(ln["text"])):
            continue
        _, _, used = _adjacent_person_at(lines, i)
        if used is None:
            continue
        consumed.add(used)
        if used > i:
            for j in range(used + 1, min(len(lines), used + 8)):
                text = _norm(lines[j]["text"])
                if not _near(lines[j - 1], lines[j]) or _is_bare_role_label(text) or not clean_person(text):
                    break
                consumed.add(j)
    keys = [_name_key(clean_person(lines[j]["text"]) or "") for j in sorted(consumed)]
    return consumed, [k for k in keys if k]


def _unlabeled_cover_author(lines: List[Line], excluded: List[frozenset], consumed: set) -> Optional[str]:
    """A personal name set on its own on the cover, above or below the title.

    Lines owned by a role label, lines with any label, and lines that continue
    a wrapped title ("... PARA" / "ADULTOS MAYORES") are skipped.
    """
    for i, ln in enumerate(lines):
        text = _norm(ln["text"])
        if i in consumed or _ANY_LABEL_RE.match(text) or _paren_role(text)[0]:
            continue
        if any(r.match(text) for r in (*_PERSON_ROLE_RES, _JURY_RE)):
            continue
        prev_text = _norm(lines[i - 1]["text"]) if i and _near(lines[i - 1], ln) else ""
        next_text = _norm(lines[i + 1]["text"]) if i + 1 < len(lines) and _near(ln, lines[i + 1]) else ""
        if (prev_text and _fold(prev_text.split()[-1]) in _AFFIL_PARTICLES) or next_text[:1].islower():
            continue
        person = clean_person(text)
        if person and _name_key(person) not in excluded:
            return person
    return None


# --------------------------------------------------------------------------
# Affiliations
# --------------------------------------------------------------------------
_AFFIL_HEAD_RE = re.compile(
    r"(?:universidad|universidade|university|universit[eé]|facultad|faculdade|faculty|escuela|escola|school|"
    r"instituto|institute|institut|centro|centre|center|departamento|department|laboratorio|laboratory)"
    r"(?![^\W\d_])",
    re.I,
)
_UNIVERSITY_HEADS = {"universidad", "universidade", "university", "universite"}
_FACULTY_HEADS = {"facultad", "faculdade", "faculty", "escuela", "escola", "school"}
_AFFIL_PARTICLES = {
    "de", "del", "la", "las", "los", "el", "y", "e", "en", "para", "of", "the", "and", "for", "in",
    "da", "do", "dos", "das",
}
_GENERIC_AFFIL = {
    "nacional", "publica", "privada", "catolica", "pontificia", "autonoma", "estatal", "provincial",
    "federal", "abierta", "tecnologica", "superior", "argentina",
}
_SEGMENT_RE = re.compile(r"\s+[–—-]\s*|\s*[–—-]\s+|\s*[|•·;]\s*|\s*[()]\s*|:\s+|,\s+(?=(?:la\s+|el\s+)?[A-ZÁÉÍÓÚÑ])")
_STATEMENT_RE = re.compile(
    r"\b(?:tesis|tesina|trabajo\s+(?:final|integrador)|disertaci[oó]n|dissertation|thesis|"
    r"para\s+(?:optar|obtener|acceder|alcanzar|aspirar)|grado\s+(?:acad[eé]mico\s+)?de|t[ií]tulo\s+de|"
    r"requisito|carrera(?:\s+de|\s*:)|programa(?:\s+de|\s*:)|doctorado|maestr[ií]a|mag[ií]ster|"
    r"especializaci[oó]n|licenciatura|degree|doctor\s+of|master\s+of|ph\.?\s?d)(?![^\W\d_])",
    re.I,
)
_PLACE_ARTICLE_RE = re.compile(
    r"\b([Dd]e)\s+(la|las|los|el)\s+(Plata|Rioja|Pampa|Matanza|Paz|Serena|Habana|Laguna|Frontera|Salle|Punta)\b"
)


def _proper_run(text: str) -> Tuple[List[str], bool]:
    """Consume a capitalized institution/program name; report if the line ended it."""
    out: List[str] = []
    for idx, tok in enumerate(text.split()):
        core = tok.strip("“”\"'«»")
        stop = False
        match = re.match(r"^(.*?)([,.;:)\]]+)$", core)
        if match and not re.fullmatch(r"(?:[A-ZÁÉÍÓÚÑ]\.){2,}", core):
            core, stop = match.group(1), True
        if core.endswith("-"):
            core, stop = core.rstrip("-"), True
        if not core or core.startswith("(") or re.search(r"\d|https?|www\.|@|\.{2,}|…", core):
            return out, False
        if idx == 0 or _fold(core) in _AFFIL_PARTICLES or core[:1].isupper():
            out.append(core)
        else:
            return out, False
        if stop:
            return out, False
    return out, True


def _trim_particles(tokens: List[str]) -> List[str]:
    tokens = list(tokens)
    while tokens and _fold(tokens[-1]) in _AFFIL_PARTICLES:
        tokens.pop()
    return tokens


def _affil_kind(head: str) -> str:
    head = _fold(head)
    if head in _UNIVERSITY_HEADS:
        return "university"
    if head in _FACULTY_HEADS:
        return "faculty"
    return "institution"


def _valid_affiliation(tokens: List[str]) -> bool:
    if len(tokens) < 2:
        return False
    rest = tokens[1:]
    if _affil_kind(tokens[0]) == "institution" and _fold(rest[0]) in {"y", "e", "and"}:
        return False
    names = [t for t in rest if _fold(t) not in _AFFIL_PARTICLES]
    if not names:
        return False
    generic = [t for t in names if _fold(t).strip(".") in _GENERIC_AFFIL]
    return len(generic) < len(names) or len(generic) >= 2


def _affil_case(tokens: List[str]) -> str:
    text = _base._smart_case(" ".join(tokens))
    return _PLACE_ARTICLE_RE.sub(lambda m: f"{m.group(1)} {m.group(2).capitalize()} {m.group(3)}", text)


_SPLIT_HEADS = _UNIVERSITY_HEADS | {"facultad", "faculdade", "faculty"}


def _split_pieces(tokens: List[str]) -> List[List[str]]:
    """Split "Facultad de Psicología de la Universidad X" into its two names.

    Only university/faculty words start a new name after a particle, so
    "Universidad Nacional del Centro" stays whole.
    """
    pieces: List[List[str]] = []
    cur: List[str] = []
    for tok in tokens:
        head = tok[:1].isupper() and _AFFIL_HEAD_RE.fullmatch(tok)
        after_particle = bool(cur) and _fold(cur[-1]) in _AFFIL_PARTICLES
        if cur and head and (_fold(tok) in _SPLIT_HEADS or not after_particle):
            pieces.append(cur)
            cur = [tok]
        else:
            cur.append(tok)
    if cur:
        pieces.append(cur)
    return [_trim_particles(p) for p in pieces]


def _segment_starts(text: str, after_statement: bool = False) -> List[int]:
    starts = [0] + [m.end() for m in _SEGMENT_RE.finditer(text)]
    # "La Universidad Nacional de Córdoba no se hace solidaria ..."
    article = re.match(r"(?i:la|el)\s+(?=[A-ZÁÉÍÓÚÑ])", text)
    if article:
        starts.append(article.end())
    if after_statement or _STATEMENT_RE.search(text):
        # Degree statements name the institution mid-sentence
        # ("Tesis presentada en la Facultad de Psicología ...").
        starts += [m.start() for m in _AFFIL_HEAD_RE.finditer(text)]
    return sorted(set(starts))


def _line_affiliations(lines: List[Line], index: int) -> List[Tuple[str, str]]:
    text = _norm(lines[index]["text"])
    found: List[Tuple[str, str]] = []
    # "Codirector: Dr. X (Universidad de Rennes)" is the advisor's affiliation.
    if any(r.match(text) for r in (*_PERSON_ROLE_RES, _JURY_RE)):
        return found
    # "Tesis para optar al título de Doctor" / "en Psicología de la Universidad Nacional de" / "Córdoba"
    after_statement = (
        index > 0 and _near(lines[index - 1], lines[index])
        and bool(_STATEMENT_RE.search(_norm(lines[index - 1]["text"])))
    )
    for start in _segment_starts(text, after_statement):
        segment = text[start:].lstrip()
        head = _AFFIL_HEAD_RE.match(segment)
        if not head or not segment[:1].isupper():
            continue
        tokens, open_end = _proper_run(segment)
        pieces = _split_pieces(tokens)
        ended_on_particle = bool(tokens) and _fold(tokens[-1]) in _AFFIL_PARTICLES
        if open_end and (ended_on_particle or not _valid_affiliation(pieces[-1])) and index + 1 < len(lines):
            nxt = lines[index + 1]
            nxt_text = _norm(nxt["text"])
            next_head = _AFFIL_HEAD_RE.match(nxt_text)
            starts_name = nxt_text[:1].isupper() or (
                bool(nxt_text.split()) and _fold(nxt_text.split()[0]) in _AFFIL_PARTICLES
            )
            if (_near(lines[index], nxt) and starts_name
                    and (not next_head or (ended_on_particle and _fold(next_head.group(0)) not in _SPLIT_HEADS))):
                tokens, _ = _proper_run(segment + " " + nxt_text)
                pieces = _split_pieces(tokens)
        for piece in pieces:
            if _valid_affiliation(piece):
                found.append((_affil_kind(piece[0]), _affil_case(piece)))
    return found


def _detect_affiliations(pages: List[List[Line]]) -> Dict[str, Optional[str]]:
    found: Dict[str, Optional[str]] = {"university": None, "faculty": None, "institution": None}
    for lines in pages:
        for i in range(len(lines)):
            for kind, value in _line_affiliations(lines, i):
                if found[kind] is None:
                    found[kind] = value
        if found["university"] and found["faculty"]:
            break
    return found


def _clean_affiliation_value(value: Any) -> Optional[str]:
    """Salvage an earlier automatic affiliation (drop trailing clauses/URLs)."""
    text = _norm(value)
    if not text or not _AFFIL_HEAD_RE.match(text) or not text[:1].isupper():
        return None
    tokens, _ = _proper_run(re.split(r"\s*[(|]|\s+[–—-]\s+", text, maxsplit=1)[0])
    pieces = _split_pieces(tokens)
    if pieces and _valid_affiliation(pieces[0]):
        return _affil_case(pieces[0])
    return None


# --------------------------------------------------------------------------
# Year, degree level and program
# --------------------------------------------------------------------------
_YEAR_RE = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")
#: «Año 2025», «Fecha: 2019», «Year 2020»: the label names the thesis date.
_YEAR_LABEL_RE = re.compile(r"(?:^|[\s,;:|])(?:a[ñn]o|fecha|year|ano|date)\s*:?\s*$", re.I)
#: A footnote opens with its call number: «1 Una cantante … nacida en 1917».
_FOOTNOTE_START_RE = re.compile(r"^\s*\d{1,3}\s+\S")


def _is_footnote(ln: Line, body_size: float) -> bool:
    """Small-print line at the foot of the page that opens with a call number."""
    size = float(ln.get("size") or 0)
    text = str(ln["text"])
    # «10 DE NOVIEMBRE DE 2014» opens with the day, not with a call number.
    if _base._MONTH_RE.search(" ".join(text.split()[:3])):
        return False
    return bool(
        _FOOTNOTE_START_RE.match(text)
        and float(ln["y0"]) >= 0.65 * float(ln.get("height") or 1)
        and body_size and size and size < body_size - 0.5
    )


def _body_size(lines: List[Line]) -> float:
    sizes = sorted(float(ln.get("size") or 0) for ln in lines if ln.get("size"))
    return sizes[len(sizes) // 2] if sizes else 0.0


def _line_years(ln: Line) -> List[Tuple[float, str]]:
    text = _norm(ln["text"])
    words = len(text.split())
    out = []
    for match in _YEAR_RE.finditer(text):
        before, after = text[:match.start()], text[match.end():]
        # Ranges inside titles ("(1944-1953)", "2021-2022") are not the thesis year.
        if re.search(r"\d{2,4}\s*[-–—/]\s*$", before) or re.match(r"^\s*[-–—/]\s*\d", after):
            continue
        # A cited work ("Smith, J. (2018). Title") dates the reference, not the thesis.
        if re.search(r"[A-ZÁÉÍÓÚÑ]\.\s*\(\s*$", before) and re.match(r"^[a-z]?\s*\)\s*[.,]", after):
            continue
        score = 0.35
        month = bool(_base._MONTH_RE.search(text))
        if month:
            score += 0.5
        # A label is a caption on a short line, not «registros del año 2007 al 2012».
        if words <= 5 and _YEAR_LABEL_RE.search(before):
            score += 0.5
        if float(ln["y0"]) >= 0.65 * float(ln.get("height") or 1):
            score += 0.12
        if _base._LOCATION_RE.match(text):
            score += 0.05
        if words <= 4:
            score += 0.1
        elif words > 12 and not month:
            score -= 0.2
        out.append((score, match.group(1)))
    return out


def _detect_year(pages: List[List[Line]]) -> Tuple[Optional[str], float]:
    best, best_conf = None, 0.0
    for page_index, lines in enumerate(pages):
        body_size = _body_size(lines)
        for ln in lines:
            if _is_footnote(ln, body_size):
                continue
            for score, year in _line_years(ln):
                adjusted = score - min(page_index, 5) * 0.03
                if adjusted > best_conf:
                    best, best_conf = year, adjusted
    return best, max(0.0, min(0.99, best_conf))


_LEVEL_RULES = (
    ("especializacion", re.compile(r"\bespecializaci[oó]n\b|\bespecialista\s+en\b", re.I)),
    ("maestria", re.compile(r"\bmaestr[ií]a\b|\bmag[ií]ster\b|\bmaster(?:'s)?\b|\bm[aá]ster\b|\bmestrado\b", re.I)),
    ("doctorado", re.compile(
        r"\bdoctorado\b|\bdoctoral\b|\bdoctor(?:a)?\s+(?:en|of)\b|\bgrado\s+de\s+doctor|\bph\.?\s?d\b|\bdoutorado\b",
        re.I)),
    ("licenciatura", re.compile(r"\blicenciatura\b|\blicenciad[oa]\s+en\b|\btesina\b", re.I)),
)
_PROGRAM_HEAD_RE = re.compile(
    r"(doctorado|maestr[ií]a|mag[ií]ster|magister|m[aá]ster|master|especializaci[oó]n|licenciatura)\s+(?:en|in|of)\s+",
    re.I,
)
_DEGREE_TITLE_RE = re.compile(
    r"\b(?:grado|t[ií]tulo)\s+(?:acad[eé]mico\s+)?de\s+"
    r"(doctor|doctora|mag[ií]ster|magister|m[aá]ster|especialista|licenciad[oa])\s+(?:en|in)\s+",
    re.I,
)
_BARE_DEGREE_TITLE_RE = re.compile(
    r"^(doctor|doctora|mag[ií]ster|magister|m[aá]ster|especialista|licenciad[oa])\s+(?:en|in)\s+", re.I
)
_DEGREE_TITLE_END_RE = re.compile(
    r"\b(?:grado|t[ií]tulo)\s+(?:acad[eé]mico\s+)?de\s+"
    r"(?:doctor|doctora|mag[ií]ster|magister|m[aá]ster|especialista|licenciad[oa])\s*$",
    re.I,
)
# Abstracts of theses with an image-only cover: "producto de la carrera de doctorado en Psicología".
_CAREER_PROGRAM_RE = re.compile(
    r"\b(?:carrera|programa)\s+(?:de\s+)?(doctorado|maestr[ií]a|especializaci[oó]n)"
    r"(?:\s+(?:en|in)\s+|\s+(?=(?-i:[A-ZÁÉÍÓÚÑ])))",  # "Carrera de Doctorado Psicología"
    re.I,
)
_PROGRAM_PREFIX_OK_RE = re.compile(
    r"(?:^|[:(–—\-]\s*|\b(?:carrera|programa|tesis|trabajo\s+final)\s+de\s+(?:la\s+)?)$", re.I
)
_PROGRAM_STOP = {"por", "que", "como", "con", "para", "mediante", "ante", "desde", "sobre", "a", "al"}
_NORMALIZED_HEADS = {
    "doctor": "Doctorado", "doctora": "Doctorado", "especialista": "Especialización",
    "licenciado": "Licenciatura", "licenciada": "Licenciatura",
}


def _is_person_line(text: str) -> bool:
    return bool(clean_person(text)) or any(r.match(text) for r in (*_PERSON_ROLE_RES, _JURY_RE))


def _line_level(text: str) -> Optional[str]:
    if not _STATEMENT_RE.search(text) or _is_person_line(text):
        return None
    hits = []
    for level, rule in _LEVEL_RULES:
        match = rule.search(text)
        if match:
            hits.append((match.start(), level))
    return min(hits)[1] if hits else None


def _discipline(text: str) -> Tuple[str, bool]:
    out: List[str] = []
    for idx, tok in enumerate(text.split()):
        if tok.startswith("("):
            return " ".join(_trim_particles(out)), False
        core = tok.strip("“”\"'«»")
        stop = False
        match = re.match(r"^(.*?)([,.;:)\]]+)$", core)
        if match:
            core, stop = match.group(1), True
        if core.endswith("-"):
            core, stop = core.rstrip("-"), True
        low = _fold(core)
        if not core or re.search(r"\d|https?", core):
            break
        if idx and low in _AFFIL_PARTICLES:
            out.append(core)
        elif core[:1].isupper():
            if _AFFIL_HEAD_RE.fullmatch(core):
                break
            out.append(core)
        elif idx < 2 and low not in _PROGRAM_STOP:
            out.append(core)
        else:
            break
        if stop:
            return " ".join(_trim_particles(out)), False
    else:
        return " ".join(_trim_particles(out)), True
    return " ".join(_trim_particles(out)), False


def _format_program(head: str, discipline: str) -> Optional[str]:
    if not discipline:
        return None
    head = _NORMALIZED_HEADS.get(_fold(head), _base._smart_case(head))
    discipline = _base._smart_case(discipline)
    return f"{head[:1].upper()}{head[1:]} en {discipline[:1].upper()}{discipline[1:]}"


def _line_program(lines: List[Line], index: int) -> Optional[str]:
    text = _norm(lines[index]["text"])
    if _is_person_line(text):
        return None
    nxt_text = _norm(lines[index + 1]["text"]) if index + 1 < len(lines) and _near(lines[index], lines[index + 1]) else ""
    candidates = []
    for match in _PROGRAM_HEAD_RE.finditer(text):
        if _PROGRAM_PREFIX_OK_RE.search(text[:match.start()]):
            candidates.append((match, match.group(1)))
    if _STATEMENT_RE.search(text):
        for match in _DEGREE_TITLE_RE.finditer(text):
            candidates.append((match, match.group(1)))
    # "... para la obtención del título de" / "DOCTORA EN PSICOLOGÍA" on its own line.
    prev = lines[index - 1] if index > 0 else None
    if (not candidates and prev is not None and _near(prev, lines[index])
            and _STATEMENT_RE.search(_norm(prev["text"]))):
        match = _BARE_DEGREE_TITLE_RE.match(text)
        if match:
            candidates.append((match, match.group(1)))
    # A degree statement may break right after "... DOCTOR EN" or "... grado de Doctor".
    if not candidates and nxt_text and (
        re.search(r"\b(?:en|in)\s*$", text, re.I)
        or (_DEGREE_TITLE_END_RE.search(text) and re.match(r"(?:en|in)\s", nxt_text, re.I))
    ):
        joined = f"{text} {nxt_text}"
        for match in _DEGREE_TITLE_RE.finditer(joined):
            candidates.append((match, match.group(1)))
        text = joined
    for match, head in sorted(candidates, key=lambda c: c[0].start()):
        discipline, open_end = _discipline(text[match.end():])
        if not discipline and open_end and nxt_text:
            discipline, _ = _discipline(nxt_text)
        program = _format_program(head, discipline)
        if program:
            return program
    return None


def _program_level(program: Optional[str]) -> Optional[str]:
    if not program:
        return None
    for level, rule in _LEVEL_RULES:
        if rule.search(program):
            return level
    return None


def _detect_degree(pages: List[List[Line]]) -> Tuple[Optional[str], Optional[str], float]:
    level = program = None
    for lines in pages:
        for i, ln in enumerate(lines):
            text = _norm(ln["text"])
            if program is None:
                program = _line_program(lines, i)
            if level is None:
                level = _line_level(text)
            if level and program:
                break
        if level and program:
            break
    level = level or _program_level(program)
    if level is None:
        for lines in pages:
            usable = [ln for ln in lines if not _is_person_line(_norm(ln["text"]))]
            level = _base._degree_level(usable)
            if level:
                break
    return level, program, 0.9 if program else 0.0


def _career_program(pages: List[List[Line]], level: Optional[str]) -> Optional[str]:
    """"Carrera/programa de doctorado en X" anywhere in the opening pages, abstracts included.

    Acknowledgements and CVs name other careers too, so a program that
    contradicts the degree level already read is not taken.
    """
    for lines in pages:
        for i, ln in enumerate(lines):
            text = _norm(ln["text"])
            nxt = _norm(lines[i + 1]["text"]) if i + 1 < len(lines) else ""
            joined = f"{text} {nxt}".strip()
            match = _CAREER_PROGRAM_RE.search(joined)
            if not match or match.start() >= len(text):
                continue
            # Continue on the next line only when this one stops right after the head.
            rest = joined[match.end():]
            discipline, _ = _discipline(rest if match.end() >= len(text) else text[match.end():])
            program = _format_program(match.group(1), discipline)
            if program and (level is None or _program_level(program) == level):
                return program
    return None


# --------------------------------------------------------------------------
# Detector
# --------------------------------------------------------------------------
_PDF_AUTHOR_JUNK = {
    "microsoft", "cuenta", "usuario", "user", "admin", "administrador", "owner", "windows", "hp",
    "lenovo", "dell", "asus", "acer", "toshiba", "samsung", "apple", "pc", "office",
}


def _clean_pdf_author(value: Any) -> Optional[str]:
    person = clean_person(value)
    if not person or any(_fold(w) in _PDF_AUTHOR_JUNK for w in person.split()):
        return None
    return person


def _set(out: Dict[str, Any], key: str, value: Optional[str], conf: float, source: str) -> None:
    meta, confidence, sources = out["metadata"], out["confidence"], out["sources"]
    if value:
        meta[key] = value
        confidence[key] = round(float(conf), 2)
        sources[key] = source
    else:
        meta.pop(key, None)
        confidence.pop(key, None)
        sources.pop(key, None)


def _clean_author_candidates(out: Dict[str, Any], people_keys: List[frozenset]) -> None:
    candidates = out.setdefault("candidates", {})
    cleaned: List[str] = []
    for value in candidates.get("author") or []:
        person = clean_person(value)
        if person and _name_key(person) not in people_keys and person not in cleaned:
            cleaned.append(person)
    if len(cleaned) >= 2:
        candidates["author"] = cleaned
        return
    candidates.pop("author", None)
    reasons = [r for r in out.get("review_reasons") or [] if r != "author_ambiguous"]
    out["review_reasons"] = reasons
    out["needs_review"] = bool(reasons)


def detect_cover_metadata(path: str | Path, filename: str | None = None) -> Dict[str, Any]:
    path = Path(path)
    out = _v04.detect_cover_metadata(path, filename)
    out["version"] = COVER_METADATA_VERSION
    if _base.fitz is None or not path.exists():
        return out

    try:
        with _base.fitz.open(path) as pdf:
            pages = [
                _base._page_lines(pdf[pno], pno)
                for pno in range(min(_MAX_FRONTMATTER_PAGES, len(pdf)))
            ]
            pdf_author = _clean_pdf_author((pdf.metadata or {}).get("author"))
    except Exception:
        return out

    out.setdefault("metadata", {})
    out.setdefault("confidence", {})
    out.setdefault("sources", {})
    previous = dict(out["metadata"])
    prev_conf = dict(out["confidence"])
    prev_sources = dict(out["sources"])
    front = [lines if _page_kind(lines) == "front" else [] for lines in pages]

    # People: explicit roles on front-matter pages, then the cleaned earlier
    # reading (unlabelled cover name or PDF metadata author).
    roles = _detect_role_people(front)
    for key in ("director", "codirector"):
        value, conf = roles[key]
        source = "frontmatter_role"
        if not value:
            value, conf, source = clean_person(previous.get(key)), prev_conf.get(key, 0.0), "frontmatter_scan"
        _set(out, key, value, conf, source)
    advisor_keys = [_name_key(out["metadata"][k]) for k in ("director", "codirector") if out["metadata"].get(k)]

    author, author_conf = roles["author"]
    author_source = "frontmatter_role"
    cover_lines = next((p for p in front if p), [])
    consumed, block_keys = _role_block_people(cover_lines)
    excluded = advisor_keys + block_keys
    if not author:
        generic = []
        if pages:
            first_author, _, alternatives = _base._detect_author(pages[0], out.get("title") or "")
            generic = [first_author, *alternatives] if first_author else []
        for value in generic:
            person = clean_person(value)
            if person and _name_key(person) not in excluded:
                author, author_conf, author_source = person, 0.86, "cover_role"
                break
    if not author:
        person = _unlabeled_cover_author(cover_lines, excluded, consumed)
        if person:
            author, author_conf, author_source = person, 0.84, "cover_role"
    if not author and pdf_author and _name_key(pdf_author) not in excluded:
        author, author_conf, author_source = pdf_author, 0.78, "pdf_metadata"
    if author and _name_key(author) in advisor_keys:
        author = None
    _set(out, "author", author, author_conf, author_source)
    _clean_author_candidates(out, advisor_keys)

    # Affiliations: proper-noun runs from front-matter pages; otherwise salvage
    # the earlier value when it is a clean institution name.
    affiliations = _detect_affiliations(front)
    for key in ("university", "faculty"):
        value, conf = affiliations[key], 0.96 if key == "university" else 0.94
        source = "frontmatter_affiliation"
        if not value:
            value, conf, source = _clean_affiliation_value(previous.get(key)), prev_conf.get(key, 0.9), "frontmatter_scan"
        affiliations[key] = value
        _set(out, key, value, conf, source)
    institution = affiliations["university"] or affiliations["institution"] or affiliations["faculty"]
    _set(out, "institution", institution, 0.94, out["sources"].get("university") or "frontmatter_affiliation")

    year, year_conf = _detect_year(front)
    if not year:
        # Only the cover itself; body pages mention many unrelated years.
        year, year_conf = _detect_year(pages[:2])
    _set(out, "year", year, year_conf, "frontmatter_date")

    level, program, program_conf = _detect_degree(front)
    program_source = "frontmatter_degree"
    if not program and previous.get("program"):
        tokens, _ = _proper_run(_norm(previous.get("program")))
        head = _PROGRAM_HEAD_RE.match(" ".join(tokens) + " ")
        if head and len(tokens) > 2:
            program = _base._smart_case(" ".join(_trim_particles(tokens)))
            program_conf, program_source = prev_conf.get("program", 0.8), "frontmatter_scan"
    if not program:
        program = _career_program(pages, level or previous.get("degree_level"))
        program_conf, program_source = 0.75, "frontmatter_statement"
    _set(out, "program", program, program_conf, program_source)
    _set(out, "degree_level", level or _program_level(program), 0.92, "frontmatter_degree")
    return out


__all__ = ["COVER_METADATA_VERSION", "clean_person", "detect_cover_metadata"]
