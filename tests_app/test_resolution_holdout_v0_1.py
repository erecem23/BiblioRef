from __future__ import annotations

from biblioref.resolver.holdout import HoldoutSource, harvest_from_message, strip_identifiers


def test_strip_identifiers_removes_doi_and_url_without_destroying_citation():
    text = "Smith, J. (2020). A useful paper. Journal X. https://doi.org/10.1234/ABC.99 https://example.org/full"
    cleaned = strip_identifiers(text)
    assert "10.1234" not in cleaned
    assert "http" not in cleaned.lower()
    assert "Smith" in cleaned
    assert "A useful paper" in cleaned


def test_harvest_uses_citing_work_reference_text_and_strips_identifier():
    source = HoldoutSource("src", "10.9999/source", "test", max_refs=2)
    message = {
        "reference": [
            {
                "key": "r1",
                "DOI": "10.1111/target.1",
                "unstructured": "García, M. (2018). Título real de una referencia depositada. Revista Uno. doi:10.1111/target.1",
            },
            {
                "key": "r2",
                "DOI": "10.2222/target.2",
                "unstructured": "Smith, A. 2019. Another deposited reference title. Journal Two. https://doi.org/10.2222/target.2",
            },
        ]
    }
    rows = harvest_from_message(source, message)
    assert len(rows) == 2
    assert rows[0]["expected_doi"] == "10.1111/target.1"
    assert rows[0]["observed_reference"].startswith("García")
    assert "10.1111/target.1" not in rows[0]["query_reference"].lower()
    assert "http" not in rows[1]["query_reference"].lower()


def test_harvest_excludes_development_gold_and_global_duplicates():
    source = HoldoutSource("src", "10.9999/source", "test", max_refs=5)
    message = {
        "reference": [
            {
                "DOI": "10.1037/h0047358",
                "unstructured": "Miller, G. A. (1956). The magical number seven plus or minus two. Psychological Review.",
            },
            {
                "DOI": "10.5555/new.1",
                "unstructured": "One, A. (2017). A sufficiently descriptive unseen target reference. Journal A.",
            },
            {
                "DOI": "10.5555/new.1",
                "unstructured": "One, A. (2017). Duplicate occurrence of the same target reference. Journal A.",
            },
        ]
    }
    seen = set()
    rows = harvest_from_message(
        source,
        message,
        excluded_dois={"10.1037/h0047358"},
        globally_seen=seen,
    )
    assert [row["expected_doi"] for row in rows] == ["10.5555/new.1"]
    assert seen == {"10.5555/new.1"}


def test_harvest_can_build_text_from_structured_deposit_fields():
    source = HoldoutSource("src", "10.9999/source", "test", max_refs=1)
    message = {
        "reference": [
            {
                "DOI": "10.5555/structured.1",
                "author": "Doe, J.",
                "year": "2014",
                "article-title": "Structured deposited title",
                "journal-title": "Journal of Structured References",
                "volume": "12",
                "first-page": "44",
            }
        ]
    }
    rows = harvest_from_message(source, message)
    assert len(rows) == 1
    assert "Structured deposited title" in rows[0]["observed_reference"]
    assert rows[0]["expected_doi"] == "10.5555/structured.1"
