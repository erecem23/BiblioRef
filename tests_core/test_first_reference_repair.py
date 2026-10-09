from copy import deepcopy
from types import SimpleNamespace

from biblioref import pipeline
from biblioref.extraction import first_reference_repair as repair
from tests_support import pdf_factory as fitz


def write_alonso_fixture(tmp_path, name="alonso.pdf"):
    pdf = tmp_path / name
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((70, 70), "Bibliografía", fontsize=14)
    page.insert_text(
        (70, 105),
        "Alonso Mielgo, A.; Sevilla Guzmán, E.; Sánchez de Puerta, F. y Guzmán Casado,",
        fontsize=9.5,
    )
    page.insert_text(
        (70, 116),
        "G. (2002): Propuestas alternativas a la agricultura industrializada.",
        fontsize=9.5,
    )
    page.insert_text(
        (70, 138),
        "Altieri, M. A. (1985). Segunda referencia.",
        fontsize=9.5,
    )
    doc.save(pdf)
    doc.close()
    return pdf


def record(text, ref_in_zone=1):
    return {
        "zone_id": 1,
        "ref_in_zone": ref_in_zone,
        "reference_text": text,
        "reference_start_page": 1,
        "reference_end_page": 1,
        "reference_start_x": 70.0,
        "zone_start_page": 1,
        "boundary_evidence": "fixture",
        "audit_flags": "",
    }


def base_report(records):
    return {
        "scope": "all_reference_sections",
        "scope_definition": "all reference sections",
        "records": records,
        "zones": [{
            "zone_id": 1,
            "heading": "Bibliografía",
            "start_page": 1,
            "end_page": 1,
            "zone_role": "primary_references",
            "start_confidence_score": 1.0,
            "start_confidence_label": "high",
            "end_confidence_score": 1.0,
            "end_confidence_label": "high",
            "zone_completeness": "complete",
            "n_segments": len(records),
            "termination_reason": "fixture",
            "adaptive_limit_exceeded": False,
        }],
        "duplicate_groups": [],
        "n_occurrences_all_zones": len(records),
        "n_unique_references": len(records),
        "n_duplicate_groups": 0,
        "n_occurrences_in_duplicate_groups": 0,
        "n_repeated_occurrences_beyond_first": 0,
        "n_records_selected": len(records),
        "detection_decision": {
            "method": "fixture",
            "requires_confirmation": False,
        },
    }


def stub_effective(monkeypatch, report):
    monkeypatch.setattr(
        pipeline,
        "_ORIGINAL_EFFECTIVE",
        lambda *args, **kwargs: deepcopy(report),
    )


def test_process_pdf_inserts_omitted_first_reference(tmp_path, monkeypatch):
    pdf = write_alonso_fixture(tmp_path)
    stub_effective(
        monkeypatch,
        base_report([
            record("Altieri, M. A. (1985). Segunda referencia."),
        ]),
    )

    result = pipeline.process_pdf(pdf, rescue_audit=False)

    assert len(result["records"]) == 2
    assert result["algorithm_version"] == "0.6.20"
    assert result["algorithm_integration"]["first_reference_repair"] == (
        "0.6.8-core-first-reference-1"
    )
    assert result["n_occurrences_all_zones"] == 2
    assert result["n_unique_references"] == 2
    assert result["n_records_selected"] == 2
    assert result["n_duplicate_groups"] == 0
    assert result["zones"][0]["n_segments"] == 2
    assert result["records"][0]["reference_text"].startswith("Alonso Mielgo")
    assert result["records"][1]["reference_text"].startswith("Altieri")
    assert result["first_reference_repairs"][0]["kind"] == "insert_omitted_first_reference"
    assert "app252" not in result["records"][0]["boundary_evidence"]


def test_process_pdf_prepends_deferred_author(tmp_path, monkeypatch):
    pdf = write_alonso_fixture(tmp_path, "alonso-deferred.pdf")
    stub_effective(
        monkeypatch,
        base_report([
            record("G. (2002): Propuestas alternativas a la agricultura industrializada."),
            record("Altieri, M. A. (1985). Segunda referencia.", 2),
        ]),
    )

    result = pipeline.process_pdf(pdf, rescue_audit=False)

    assert len(result["records"]) == 2
    assert result["records"][0]["reference_text"].startswith("Alonso Mielgo")
    assert "(2002)" in result["records"][0]["reference_text"]
    assert result["first_reference_repairs"][0]["kind"] == "prepend_deferred_author"


def physical_lines(*texts):
    return [
        SimpleNamespace(text=text, x0=70.0)
        for text in texts
    ]


def test_repair_function_inserts_complete_omitted_reference(tmp_path):
    pdf = write_alonso_fixture(tmp_path, "helper-insert.pdf")
    original = [record("Altieri, M. A. (1985). Segunda referencia.")]

    repaired, repairs = repair.apply_first_reference_repair(
        pdf,
        base_report(original)["zones"],
        original,
    )

    assert [item["reference_text"] for item in repaired][0].startswith("Alonso Mielgo")
    assert repaired[1]["reference_text"].startswith("Altieri")
    assert repairs[0]["kind"] == "insert_omitted_first_reference"
    assert repaired[0]["boundary_evidence"] == (
        "core_first_reference_repair_v0_6_8+insert_omitted_first_reference"
    )


def test_repair_function_prepends_deferred_author(tmp_path):
    pdf = write_alonso_fixture(tmp_path, "helper-prepend.pdf")
    original = [
        record("G. (2002): Propuestas alternativas a la agricultura industrializada."),
        record("Altieri, M. A. (1985). Segunda referencia.", 2),
    ]

    repaired, repairs = repair.apply_first_reference_repair(
        pdf,
        base_report(original)["zones"],
        original,
    )

    assert repaired[0]["reference_text"].startswith("Alonso Mielgo")
    assert "(2002)" in repaired[0]["reference_text"]
    assert repairs[0]["kind"] == "prepend_deferred_author"
    assert repaired[0]["boundary_evidence"].endswith(
        "core_first_reference_repair_v0_6_8+prepend_deferred_author"
    )


def run_with_physical_lines(monkeypatch, lines, original=None):
    original = original or [
        record("Altieri, M. A. (1985). Segunda referencia.")
    ]
    monkeypatch.setattr(
        repair,
        "extract_layout_lines_range",
        lambda *args, **kwargs: physical_lines(*lines),
    )
    repaired, repairs = repair.apply_first_reference_repair(
        "fixture.pdf",
        base_report(original)["zones"],
        original,
    )
    return original, repaired, repairs


def test_repair_abstains_without_explicit_heading(monkeypatch):
    original, repaired, repairs = run_with_physical_lines(
        monkeypatch,
        [
            "Alonso Mielgo, A.; Sevilla Guzmán, E.",
            "G. (2002): Propuestas alternativas.",
            "Altieri, M. A. (1985). Segunda referencia.",
        ],
    )

    assert repairs == []
    assert repaired == original


def test_repair_abstains_without_physical_prefix(monkeypatch):
    original, repaired, repairs = run_with_physical_lines(
        monkeypatch,
        [
            "Bibliografía",
            "Altieri, M. A. (1985). Segunda referencia.",
        ],
    )

    assert repairs == []
    assert repaired == original


def test_repair_abstains_with_weak_author_evidence(monkeypatch):
    original, repaired, repairs = run_with_physical_lines(
        monkeypatch,
        [
            "Bibliografía",
            "Una nota introductoria",
            "Altieri, M. A. (1985). Segunda referencia.",
        ],
    )

    assert repairs == []
    assert repaired == original


def test_repair_abstains_for_undated_prefix_and_non_deferred_record(monkeypatch):
    original, repaired, repairs = run_with_physical_lines(
        monkeypatch,
        [
            "Bibliografía",
            "Alonso Mielgo, A.",
            "Altieri, M. A. (1985). Segunda referencia.",
        ],
    )

    assert repairs == []
    assert repaired == original


def test_repair_abstains_when_first_record_is_not_physically_matchable(monkeypatch):
    original, repaired, repairs = run_with_physical_lines(
        monkeypatch,
        [
            "Bibliografía",
            "Alonso Mielgo, A.; Sevilla Guzmán, E. (2002). Primera referencia.",
            "Otra persona, B. (2005). Registro físico diferente.",
        ],
    )

    assert repairs == []
    assert repaired == original


def test_repair_abstains_when_layout_acquisition_fails(monkeypatch):
    original = [record("Altieri, M. A. (1985). Segunda referencia.")]

    def fail_layout(*args, **kwargs):
        raise RuntimeError("layout unavailable")

    monkeypatch.setattr(repair, "extract_layout_lines_range", fail_layout)
    repaired, repairs = repair.apply_first_reference_repair(
        "fixture.pdf",
        base_report(original)["zones"],
        original,
    )

    assert repairs == []
    assert repaired == original



def test_repair_abstains_when_page_evidence_is_malformed():
    original = [record("Altieri, M. A. (1985). Segunda referencia.")]
    original[0]["reference_start_page"] = "not-a-page"

    repaired, repairs = repair.apply_first_reference_repair(
        "fixture.pdf",
        base_report(original)["zones"],
        original,
    )

    assert repairs == []
    assert repaired == original


def test_repair_abstains_when_prefix_x_is_malformed(monkeypatch):
    original = [record("Altieri, M. A. (1985). Segunda referencia.")]
    lines = [
        SimpleNamespace(text="Bibliografía", x0=70.0),
        SimpleNamespace(
            text="Alonso Mielgo, A. (2002). Primera referencia.",
            x0=None,
        ),
        SimpleNamespace(
            text="Altieri, M. A. (1985). Segunda referencia.",
            x0=70.0,
        ),
    ]
    monkeypatch.setattr(
        repair,
        "extract_layout_lines_range",
        lambda *args, **kwargs: lines,
    )

    repaired, repairs = repair.apply_first_reference_repair(
        "fixture.pdf",
        base_report(original)["zones"],
        original,
    )

    assert repairs == []
    assert repaired == original


def test_reconciliation_updates_only_repaired_zone_segment_count(monkeypatch):
    first = record("Altieri, M. A. (1985). Segunda referencia.")
    second = {
        **record("Otra autora, B. (2001). Zona sin cambios."),
        "zone_id": 2,
    }
    report = base_report([first])
    report["zones"].append({
        **report["zones"][0],
        "zone_id": 2,
        "heading": "Referencias",
        "n_segments": 1,
    })
    report["records"].append(second)
    report["n_occurrences_all_zones"] = 2
    report["n_unique_references"] = 2
    report["n_records_selected"] = 2
    inserted = {
        **first,
        "reference_text": "Alonso Mielgo, A. (2002). Primera referencia.",
        "ref_in_zone": 1,
    }
    shifted_first = {**first, "ref_in_zone": 2}

    monkeypatch.setattr(
        pipeline,
        "apply_first_reference_repair",
        lambda *args, **kwargs: (
            [inserted, shifted_first, second],
            [{
                "zone_id": 1,
                "kind": "insert_omitted_first_reference",
                "page": 1,
                "text": inserted["reference_text"],
            }],
        ),
    )

    result = pipeline._apply_first_reference_reconciliation(
        "fixture.pdf",
        report,
    )

    assert result["zones"][0]["n_segments"] == 2
    assert result["zones"][1]["n_segments"] == 1
    assert [item["zone_id"] for item in result["records"]] == [1, 1, 2]


def write_duplicate_repair_fixture(tmp_path):
    pdf = tmp_path / "duplicate-repair.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((70, 70), "Bibliografía", fontsize=14)
    page.insert_text(
        (70, 105),
        "Alonso Mielgo, A. (2002). Primera referencia.",
        fontsize=9.5,
    )
    page.insert_text(
        (70, 127),
        "Altieri, M. A. (1985). Segunda referencia.",
        fontsize=9.5,
    )
    page.insert_text(
        (70, 149),
        "Alonso Mielgo, A. (2002). Primera referencia.",
        fontsize=9.5,
    )
    doc.save(pdf)
    doc.close()
    return pdf


def duplicate_pre_repair_report():
    return base_report([
        record("Altieri, M. A. (1985). Segunda referencia."),
        record("Alonso Mielgo, A. (2002). Primera referencia.", 2),
    ])


def test_repaired_records_rebuild_duplicate_metadata(tmp_path, monkeypatch):
    pdf = write_duplicate_repair_fixture(tmp_path)
    stub_effective(monkeypatch, duplicate_pre_repair_report())

    result = pipeline.process_pdf(pdf, rescue_audit=False)

    assert result["n_occurrences_all_zones"] == 3
    assert result["n_unique_references"] == 2
    assert result["n_records_selected"] == 3
    assert result["n_duplicate_groups"] == 1
    assert result["n_occurrences_in_duplicate_groups"] == 2
    assert result["n_repeated_occurrences_beyond_first"] == 1
    assert result["duplicate_groups"][0]["occurrence_count"] == 2


def test_unique_scope_is_selected_from_repaired_all_zones(tmp_path, monkeypatch):
    pdf = write_duplicate_repair_fixture(tmp_path)
    stub_effective(monkeypatch, duplicate_pre_repair_report())

    result = pipeline.process_pdf(
        pdf,
        scope="unique_references",
        rescue_audit=False,
    )

    assert result["scope"] == "unique_references"
    assert result["n_occurrences_all_zones"] == 3
    assert result["n_unique_references"] == 2
    assert result["n_records_selected"] == 2
    assert len(result["records"]) == 2
    assert [item["reference_text"] for item in result["records"]] == [
        "Alonso Mielgo, A. (2002). Primera referencia.",
        "Altieri, M. A. (1985). Segunda referencia.",
    ]
