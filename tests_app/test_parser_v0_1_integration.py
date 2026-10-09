import csv
from pathlib import Path

import app
from biblioref.parsing.legacy import PARSER_STATUS, PARSER_VERSION, parse_reference, parse_reference_legacy
from biblioref.parsing import PARSER_VERSION as CURRENT_PARSER_VERSION
from tests_support.private_data import private_data

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "parser_baseline" / "agrazar_v0_8_9_parsed_legacy_v0_1.csv"


def _cell(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "True" if value else "False"
    return str(value)


def test_legacy_port_matches_all_432_frozen_agrazar_rows():
    fields = [
        "parser_version", "autor_final", "autores_normalizados", "anio_edicion",
        "tipo_documento", "es_revista", "titulo", "revista_canonica",
        "revista_norm", "fuente_editorial", "doi", "cita_cruda",
    ]
    with private_data(BASELINE).open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 432
    for i, row in enumerate(rows):
        parsed = parse_reference_legacy(row["reference_text"])
        for field in fields:
            assert _cell(parsed.get(field)) == row.get(field, ""), (i, field, parsed.get(field), row.get(field))


def test_public_parser_schema_is_downstream_and_auditable():
    p = parse_reference("Smith, J. (2020). Example title. Journal of Examples, 12(3), 20-31. https://doi.org/10.1234/example")
    assert p["parser_version"] == PARSER_VERSION
    assert p["parser_status"] == PARSER_STATUS == "development_baseline"
    assert p["author"] == "Smith, J"
    assert p["year"] == "2020"
    assert p["publication_type"] == "articulo_revista"
    assert p["doi"] == "10.1234/example"


def test_app_record_gets_nested_parse_without_replacing_raw_text():
    raw = "Freud, S. (1915). Pulsiones y destinos de pulsión."
    rec = app._record_to_ui({"reference_text": raw, "zone_id": 1, "reference_start_page": 2}, 1)
    assert rec["text"] == raw
    assert rec["parsed"]["author"] == "Freud, S."
    assert rec["parsed"]["year"] == "1915"
    assert rec["parsed"]["parser_version"] == CURRENT_PARSER_VERSION == "biblioref-parser-v0.12.8"


def test_app_reparse_tracks_human_text_change():
    rec = {"text": "Doe, J. (2001). Old title."}
    app._refresh_reference_parse(rec)
    assert rec["parsed"]["year"] == "2001"
    rec["text"] = "Doe, J. (2004). New title."
    app._refresh_reference_parse(rec)
    assert rec["parsed"]["year"] == "2004"
    assert rec["parsed"]["title"] == "New title"


def test_parser_not_imported_by_core_pipeline():
    source = (ROOT / "biblioref" / "pipeline.py").read_text(encoding="utf-8")
    assert "biblioref.parsing" not in source
