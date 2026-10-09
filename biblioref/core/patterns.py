"""Cross-stage bibliographic evidence patterns."""

import re

YEAR_OR_SOURCE_RX = re.compile(
    r"(?:\b(?:18|19|20)\d{2}[a-z]?\b|https?://|www\.|\bdoi\s*:|"
    r"\b(?:ley|decreto|resoluci[oó]n|exp(?:te|ediente))\b)",
    re.I,
)

#: Cola de lista de autores sin terminar: "& Olivier-Abbal, P.", ",&Farkas, T.",
#: "... & Lehéricy, S.".  Una referencia completa no termina así: termina en año,
#: páginas, editorial, DOI o URL.  Separa una entrada de autor repetido —"(1995).
#: Título…" después de una referencia completa— de la continuación de un registro
#: cuyo año se fue a la línea siguiente porque la lista de autores ocupó la
#: primera entera.
AUTHOR_LIST_TAIL_RX = re.compile(
    r"(?:&|\by\b|,|\.\.\.|…)\s*[A-ZÁÉÍÓÚÑÜ][\w'’\-]+,\s*"
    r"[A-ZÁÉÍÓÚÑÜ]\.(?:\s*[A-ZÁÉÍÓÚÑÜ]\.)*\s*$"
)
