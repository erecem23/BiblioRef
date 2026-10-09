# -*- coding: utf-8 -*-
"""OpenAlex search-parameter sanitation v0.2.

OpenAlex answers HTTP 400 for some punctuation in ``search`` rather than
ignoring it. In the 2026-09-18 calibration run every 400 came from a title
phrased as a question, and 989 references in the corpus (3,0 %) have one.
"""
from urllib.parse import parse_qs, urlparse

from biblioref.resolver.models import ResolverQuery
from biblioref.resolver.openalex import OpenAlexBackend, search_text


class RecordingTransport:
    def __init__(self):
        self.urls = []

    def __call__(self, url, headers, timeout):
        self.urls.append(url)
        return {"results": []}


def _search_param(query):
    transport = RecordingTransport()
    OpenAlexBackend(transport=transport).search(query)
    assert transport.urls, "no se emitió ningún pedido"
    return parse_qs(urlparse(transport.urls[-1]).query)["search"][0]


def test_a_question_title_loses_only_its_punctuation():
    assert search_text("Does performance on theory of mind tasks decline in old age?") == (
        "Does performance on theory of mind tasks decline in old age"
    )


def test_spanish_opening_question_mark_is_dropped_too():
    assert search_text("¿Cómo se estudia el desarrollo de la mente?") == (
        "Cómo se estudia el desarrollo de la mente"
    )


def test_accents_and_hyphens_survive():
    assert search_text("Neurobiología del self-report en niños") == (
        "Neurobiología del self-report en niños"
    )


def test_quotes_and_colons_become_spaces():
    assert search_text('¿Does the autistic child have a "theory of mind"?') == (
        "Does the autistic child have a theory of mind"
    )
    assert search_text("Teoría de la mente: evolución y ontogenia") == (
        "Teoría de la mente evolución y ontogenia"
    )


def test_an_ordinary_title_is_untouched():
    title = "Machine learning in psychology"
    assert search_text(title) == title


def test_the_request_carries_the_sanitised_text():
    query = ResolverQuery(
        raw_reference="x",
        title='Is there a "language of the eyes"? Evidence from normal adults',
        year="1997",
    )
    sent = _search_param(query)
    assert "?" not in sent
    assert '"' not in sent
    assert sent == "Is there a language of the eyes Evidence from normal adults"


def test_a_doi_lookup_is_not_touched_by_sanitation():
    transport = RecordingTransport()
    OpenAlexBackend(transport=transport).search(
        ResolverQuery(raw_reference="x", doi="10.1234/abc")
    )
    assert "doi:https://doi.org/10.1234/abc" in transport.urls[-1].replace("%3A", ":").replace("%2F", "/")


def test_a_title_of_only_punctuation_sends_nothing():
    transport = RecordingTransport()
    got = OpenAlexBackend(transport=transport).search(
        ResolverQuery(raw_reference="", title="¿?¡!")
    )
    assert got == ()
    assert transport.urls == []
