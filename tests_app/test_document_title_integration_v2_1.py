from pathlib import Path

from tests_support import pdf_factory as fitz

import app
from biblioref.document_title_v24 import TITLE_READING_REVISION
from biblioref.metadata import COVER_METADATA_VERSION
from biblioref.metadata.integration import install_cover_metadata

install_cover_metadata(app)


def _cover(path: Path):
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((70, 105), "UNIVERSIDAD NACIONAL DEL LITORAL", fontsize=15)
    page.insert_text((95, 280), "Procesos colectivos y subjetividad", fontsize=18)
    page.insert_text((145, 312), "en espacios educativos", fontsize=18)
    page.insert_text((190, 430), "Tesis de doctorado", fontsize=12)
    page.insert_text((205, 500), "Carla Méndez", fontsize=12)
    doc.save(path)
    doc.close()


def test_title_revision_refreshes_independently_from_cover_metadata_revision(tmp_path):
    path = tmp_path / "tesis.pdf"
    _cover(path)
    item = {
        "thesis_id": "T9101",
        "title": "Universidad Nacional del Litoral",
        "title_source": "cover_layout",
        "title_confirmed": False,
        "metadata": {"author": "Autora verificada"},
        "metadata_detection": {"suggestions": {"author": "Autora verificada"}},
        "cover_metadata_revision": COVER_METADATA_VERSION,
        "path": str(path),
        "filename": path.name,
    }

    changed = app._ensure_doc_identity(item)

    assert changed is True
    assert item["title"] == "Procesos colectivos y subjetividad en espacios educativos"
    assert item["title_reading_revision"] == TITLE_READING_REVISION
    assert item["cover_metadata_revision"] == COVER_METADATA_VERSION
    assert item["metadata"]["author"] == "Autora verificada"


def test_title_revision_never_overwrites_human_title(tmp_path):
    path = tmp_path / "tesis.pdf"
    _cover(path)
    item = {
        "thesis_id": "T9102",
        "title": "Título corregido manualmente",
        "title_source": "human",
        "title_confirmed": True,
        "metadata": {},
        "cover_metadata_revision": COVER_METADATA_VERSION,
        "path": str(path),
        "filename": path.name,
    }

    app._ensure_doc_identity(item)

    assert item["title"] == "Título corregido manualmente"
    assert item["title_reading_revision"] == TITLE_READING_REVISION
    assert item["cover_metadata_revision"] == COVER_METADATA_VERSION
