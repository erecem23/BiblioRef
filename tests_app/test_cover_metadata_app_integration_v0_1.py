from pathlib import Path

from tests_support import pdf_factory as fitz

import app
from biblioref.metadata import COVER_METADATA_VERSION
from biblioref.metadata.integration import install_cover_metadata

install_cover_metadata(app)


def _cover(path: Path):
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    lines = [
        (100, "UNIVERSIDAD NACIONAL DEL LITORAL", 14),
        (125, "FACULTAD DE HUMANIDADES", 14),
        (275, "TESIS DE MAESTRÍA", 14),
        (305, "Procesos colectivos y subjetividad en espacios educativos", 14),
        (415, "Para obtener el título de", 12),
        (438, "Magister en Psicología Social", 14),
        (520, "Presenta:", 12),
        (544, "Lic. Carla Méndez", 14),
        (570, "Directora", 12),
        (594, "Dra. Andrea López", 14),
        (715, "Mayo 2015", 12),
    ]
    for y, text, size in lines:
        page.insert_text((70, y), text, fontsize=size)
    doc.save(path)
    doc.close()


def test_old_unconfirmed_project_gets_cover_metadata_migration(tmp_path):
    path = tmp_path / "tesis.pdf"
    _cover(path)
    item = {
        "thesis_id": "T0001",
        "title": "Para obtener el título de Magister en Psicología Social",
        "title_source": "cover_layout",
        "title_confirmed": False,
        "metadata": {},
        "path": str(path),
        "filename": path.name,
    }
    changed = app._ensure_doc_identity(item)
    assert changed is True
    assert item["title"] == "Procesos colectivos y subjetividad en espacios educativos"
    assert item["metadata"]["author"] == "Carla Méndez"
    assert item["metadata"]["year"] == "2015"
    assert item["metadata"]["university"] == "Universidad Nacional del Litoral"
    assert item["metadata"]["faculty"] == "Facultad de Humanidades"
    assert item["metadata"]["program"] == "Magister en Psicología Social"
    assert item["cover_metadata_revision"] == COVER_METADATA_VERSION
    assert item["metadata_detection"]["confidence"]["author"] >= 0.9


def test_cover_migration_never_overwrites_human_title_or_existing_metadata(tmp_path):
    path = tmp_path / "tesis.pdf"
    _cover(path)
    item = {
        "thesis_id": "T0002",
        "title": "Título confirmado por usuario",
        "title_source": "human",
        "title_confirmed": True,
        "metadata": {"author": "Autora verificada", "year": "2014"},
        "path": str(path),
        "filename": path.name,
    }
    app._ensure_doc_identity(item)
    assert item["title"] == "Título confirmado por usuario"
    assert item["metadata"]["author"] == "Autora verificada"
    assert item["metadata"]["year"] == "2014"
    assert item["metadata"]["university"] == "Universidad Nacional del Litoral"
