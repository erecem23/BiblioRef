import csv
import json
import zipfile
from pathlib import Path

from field_test_bundle import build_bundle
from biblioref.parsing.v11 import parse_reference


def test_field_test_bundle_is_diagnostic_only(tmp_path):
    src = tmp_path / "sample.csv"
    fields = [
        "thesis_id","thesis_title","filename","document_id","reference_id","author","year","university","faculty","program","repository","area","country","order","text","start_page","end_page","zone_id","status","source","edited",
        "parsed_parser_version","parsed_parser_status","parsed_parse_style","parsed_author","parsed_authors","parsed_year","parsed_publication_type","parsed_title","parsed_journal","parsed_publisher","parsed_publisher_observed","parsed_source_publisher","parsed_doi",
    ]
    texts = [
        "Smith, J. (2020). Example. Journal, 1(2), 3-4.",
        "Brown, A. (2021). Example 2. Journal, 2(1), 4-5.",
        "White, C. (2022). Example 3. Journal, 3(1), 5-6.",
    ]
    with src.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields); w.writeheader()
        for i, text in enumerate(texts, 1):
            p = parse_reference(text)
            row = {k: "" for k in fields}
            row.update({"thesis_id":"T1","document_id":"D1","reference_id":f"R{i}","order":i,"text":text,"zone_id":"1"})
            for key in ("parser_version","parser_status","parse_style","author","authors","year","publication_type","title","journal","publisher","publisher_observed","source_publisher","doi"):
                value = p.get(key)
                if isinstance(value, (list, dict)): value = json.dumps(value, ensure_ascii=False)
                row[f"parsed_{key}"] = value or ""
            w.writerow(row)
    before = src.read_bytes()
    bundle = build_bundle(src, tmp_path / "out")
    assert src.read_bytes() == before
    assert bundle.exists()
    with zipfile.ZipFile(bundle) as zf:
        names = zf.namelist()
        assert any(n.endswith("_manifest.json") for n in names)
        assert any(n.endswith("_style_profile.json") for n in names)
        manifest_name = next(n for n in names if n.endswith("_manifest.json"))
        manifest = json.loads(zf.read(manifest_name))
        assert manifest["input"]["n_references"] == 3
        assert manifest["versions"]["core_mutated_by_helper"] is False
