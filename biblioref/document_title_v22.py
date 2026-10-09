from __future__ import annotations

"""Narrow title-reading revision that blocks administrative front-matter labels.

This layer intentionally reuses the validated document-title v2.1 geometry and
scoring. It only extends the role vocabulary so tribunal/jury/committee text
cannot compete with a real thesis title.
"""
from pathlib import Path

from . import document_title as _base

TITLE_READING_REVISION = "document-title-v2.2"

ADMIN_ROLE_TERMS = (
    "tribunal evaluador", "tribunal de tesis", "tribunal examinador", "miembros del tribunal",
    "jurado", "jurado evaluador", "jurado de tesis", "miembros del jurado",
    "comité evaluador", "comite evaluador", "comité de tesis", "comite de tesis",
    "comisión evaluadora", "comision evaluadora", "evaluadores", "evaluador:", "evaluadora:",
    "evaluation committee", "examining committee", "examination committee", "thesis committee",
    "doctoral committee", "jury", "examiners", "examiner:", "review committee",
    "banca examinadora", "banca de defesa", "membros da banca", "comissão julgadora", "comissao julgadora",
)

# document_title.py resolves ROLE_TERMS at runtime. Extending the module global
# preserves every previous heuristic while turning these labels into hard
# barriers and strong negative evidence for PDF metadata candidates as well.
_base.ROLE_TERMS = tuple(dict.fromkeys((*_base.ROLE_TERMS, *ADMIN_ROLE_TERMS)))


def detect_thesis_title(path: Path, filename: str) -> tuple[str, str]:
    return _base.detect_thesis_title(Path(path), str(filename))


__all__ = ["TITLE_READING_REVISION", "ADMIN_ROLE_TERMS", "detect_thesis_title"]
