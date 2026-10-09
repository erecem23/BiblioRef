"""A thesis with more paragraphs left out than references taken goes to «revisar».

T0145 finished «lista» with 19 references and 72 possible missing: the engine's
own audit looked consistent, and the coverage check was only a message.
"""
import app


def _result(n_records, n_missing):
    return {
        "records": [{"reference_text": f"Ref {i}"} for i in range(n_records)],
        "post_extraction_audit": {"status": "looks_consistent"},
        "coverage_report": {"summary": {"n_possible_missing": n_missing}},
    }


def test_more_missing_than_taken_needs_review():
    summary = app._analysis_summary(_result(19, 72))
    assert summary["needs_review"]
    assert any("incompleta" in m for m in summary["messages"])


def test_a_few_missing_do_not_change_the_status():
    assert not app._analysis_summary(_result(200, 18))["needs_review"]
    # Short lists: under ten paragraphs left out is not enough evidence.
    assert not app._analysis_summary(_result(3, 8))["needs_review"]
