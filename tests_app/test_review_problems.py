from pathlib import Path

from biblioref.review_problems import data_check_id, merged_check_id, problem_counts


def _doc(**extra):
    doc = {
        "id": "d1", "updated_at": 1, "n_references": 3,
        "analysis": {"coverage": {
            "possible_missing": [{"id": "m1", "page": 33}, {"id": "m2", "page": 34}],
            "merged_suspects": [{"record_index": 3, "page": 35, "text": "x"}],
            "page_boundaries": [{"id": "b1", "verdict": "review"}, {"id": "b2", "verdict": "continue"}],
        }},
        "references": [
            {"id": "r1", "parsed": {"author": "Allport", "year": "1954", "publication_type": "sin_clasificar"}},
            {"id": "r2", "parsed": {"author": "", "year": "", "publication_type": "libro"}},
            {"id": "r3", "parsed": {"author": "", "publication_type": ""}, "parsed_review": {"overrides": {"author": "Hair", "year": "2019"}}},
            {"id": "r4", "deleted": True, "parsed": {}},
        ],
    }
    doc.update(extra)
    return doc


def test_counts_every_kind_from_stored_data():
    assert problem_counts(_doc()) == {"missing": 2, "merged": 1, "boundaries": 1, "type": 2, "author": 1, "year": 1}


def test_decisions_and_human_corrections_remove_items():
    decisions = {
        "m1": {"decision": "ignore"},
        merged_check_id({"record_index": 3, "page": 35}): {"decision": "ignore"},
        "b1": {"decision": "continue"},
        data_check_id("type", "r1"): {"decision": "ignore"},
    }
    counts = problem_counts(_doc(id="d2", audit_decisions=decisions))
    assert counts == {"missing": 1, "merged": 0, "boundaries": 0, "type": 1, "author": 1, "year": 1}


def test_ui_shows_problems_everywhere_and_walks_them_one_by_one():
    js = Path("static/review-problems.js").read_text(encoding="utf-8")
    for text in ("Para revisar en", "Está bien", "No es una referencia", "Revisar el borde…", "Dividir…", "← → para moverte"):
        assert text in js
    assert "window.BiblioRefRefFilter" in js and "window.BiblioRefProblems" in js
    sheet = Path("static/project-reference-sheet.js").read_text(encoding="utf-8")
    assert "BiblioRefProblems.chips(d, {arrow: true})" in sheet and "data-sort-problems" in sheet
    assert "BiblioRefProblems.chips" in Path("static/project-organize.js").read_text(encoding="utf-8")
    assert "review-problems.js?v=5" in Path("static/projects.js").read_text(encoding="utf-8")
