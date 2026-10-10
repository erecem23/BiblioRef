"""Export and console robustness found in the IJDL structural evaluation."""

import csv
import io
import json

from biblioref.exporters import write_csv_rows
from biblioref.interfaces import cli


def test_csv_header_is_union_of_record_keys(tmp_path):
    rows = [
        {"reference_text": "(1) A", "zone_id": 1},
        {"reference_text": "(2) B", "zone_id": 1, "boundary_reconciliation_version": "0.6.5"},
    ]
    out = write_csv_rows(rows, tmp_path / "references.csv")
    with open(out, encoding="utf-8-sig", newline="") as handle:
        read = list(csv.DictReader(handle))
    assert list(read[0]) == ["reference_text", "zone_id", "boundary_reconciliation_version"]
    assert read[0]["boundary_reconciliation_version"] == ""
    assert read[1]["boundary_reconciliation_version"] == "0.6.5"


def test_cli_summary_survives_console_without_the_character(tmp_path, monkeypatch):
    result = {
        "software_version": "test",
        "n_zones": 1,
        "records": [{"reference_text": "(1) λ-calculus", "zone_id": 1}],
        "zones": [{"zone_id": 1, "heading": "References"}],
        "detection_decision": {"reason": "λ"},
    }
    monkeypatch.setattr(cli, "process_pdf", lambda *args, **kwargs: result)
    buffer = io.BytesIO()
    console = io.TextIOWrapper(buffer, encoding="cp1252")
    monkeypatch.setattr(cli.sys, "stdout", console)
    json_out = tmp_path / "result.json"
    code = cli.main(["thesis.pdf", "--json", str(json_out), "--csv", str(tmp_path / "references.csv")])
    console.flush()
    assert code == 0
    assert json.loads(json_out.read_text(encoding="utf-8"))["records"][0]["reference_text"] == "(1) λ-calculus"
    assert "\\u03bb" in buffer.getvalue().decode("cp1252")
