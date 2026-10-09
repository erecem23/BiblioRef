from urllib.parse import parse_qs, urlparse

from biblioref.resolver import CrossrefBackend, ResolverQuery


def test_crossref_exact_doi_uses_work_endpoint_and_maps_metadata():
    seen = {}

    def transport(url, headers, timeout):
        seen["url"] = url
        seen["headers"] = headers
        seen["timeout"] = timeout
        return {
            "status": "ok",
            "message": {
                "DOI": "10.1234/ABC.1",
                "title": ["A resolved work"],
                "author": [{"family": "Pérez", "given": "Ana"}],
                "published-print": {"date-parts": [[2019, 6]]},
                "container-title": ["Revista de Prueba"],
                "publisher": "Editorial X",
                "type": "journal-article",
                "URL": "https://doi.org/10.1234/ABC.1",
            },
        }

    backend = CrossrefBackend(email="test@example.org", transport=transport)
    got = backend.search(ResolverQuery(raw_reference="x", doi="10.1234/abc.1"))

    assert len(got) == 1
    assert got[0].doi == "10.1234/abc.1"
    assert got[0].title == "A resolved work"
    assert got[0].authors == ("Pérez, Ana",)
    assert got[0].year == "2019"
    assert got[0].container_title == "Revista de Prueba"
    assert got[0].retrieval_method == "doi_exact"
    assert got[0].rank == 1
    assert "/works/10.1234%2Fabc.1" in seen["url"]
    assert parse_qs(urlparse(seen["url"]).query)["mailto"] == ["test@example.org"]
    assert "BiblioRef-metadata-resolver" in seen["headers"]["User-Agent"]


def test_crossref_free_reference_uses_query_bibliographic_and_preserves_provider_score():
    seen = {}

    def transport(url, headers, timeout):
        seen["url"] = url
        return {
            "message": {
                "items": [
                    {
                        "DOI": "10.5555/one",
                        "title": ["Candidate one"],
                        "author": [{"family": "García", "given": "María"}],
                        "issued": {"date-parts": [[2020]]},
                        "score": 84.7,
                    },
                    {
                        "DOI": "10.5555/two",
                        "title": ["Candidate two"],
                        "author": [{"family": "García", "given": "María"}],
                        "issued": {"date-parts": [[2021]]},
                        "score": 52.1,
                    },
                ]
            }
        }

    raw = "García, M. (2020). Candidate one."
    backend = CrossrefBackend(rows=2, transport=transport)
    got = backend.search(ResolverQuery(raw_reference=raw))

    params = parse_qs(urlparse(seen["url"]).query)
    assert params["query.bibliographic"] == [raw]
    assert params["rows"] == ["2"]
    assert [x.rank for x in got] == [1, 2]
    assert [x.provider_score for x in got] == [84.7, 52.1]
    assert all(x.retrieval_method == "query_bibliographic" for x in got)


def test_crossref_empty_query_abstains_without_network_call():
    def transport(url, headers, timeout):
        raise AssertionError("transport should not be called")

    backend = CrossrefBackend(transport=transport)
    assert backend.search(ResolverQuery(raw_reference="")) == ()


def test_crossref_rows_are_bounded_to_small_candidate_set():
    low = CrossrefBackend(rows=0, transport=lambda *args: {"message": {"items": []}})
    high = CrossrefBackend(rows=999, transport=lambda *args: {"message": {"items": []}})
    assert low.rows == 1
    assert high.rows == 20
