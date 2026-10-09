from urllib.parse import parse_qs, urlparse

from biblioref.resolver import OpenAlexBackend, ResolverQuery


def test_openalex_exact_doi_uses_filter_and_maps_work():
    seen = {}

    def transport(url, headers, timeout):
        seen["url"] = url
        seen["headers"] = headers
        return {
            "results": [
                {
                    "id": "https://openalex.org/W123",
                    "doi": "https://doi.org/10.1234/ABC.1",
                    "title": "A resolved work",
                    "publication_year": 2019,
                    "authorships": [
                        {"author": {"display_name": "Ana Pérez"}},
                        {"author": {"display_name": "Juan García"}},
                    ],
                    "primary_location": {
                        "source": {"display_name": "Revista de Prueba"}
                    },
                    "type": "article",
                    "relevance_score": 91.2,
                }
            ]
        }

    backend = OpenAlexBackend(api_key="secret", transport=transport)
    got = backend.search(ResolverQuery(raw_reference="x", doi="10.1234/abc.1"))

    params = parse_qs(urlparse(seen["url"]).query)
    assert params["filter"] == ["doi:https://doi.org/10.1234/abc.1"]
    assert got[0].source_id == "https://openalex.org/W123"
    assert got[0].doi == "10.1234/abc.1"
    assert got[0].authors == ("Ana Pérez", "Juan García")
    assert got[0].year == "2019"
    assert got[0].container_title == "Revista de Prueba"
    assert got[0].provider_score == 91.2
    assert got[0].retrieval_method == "doi_exact"
    assert seen["headers"]["Authorization"] == "Bearer secret"


def test_openalex_prefers_parser_title_and_filters_by_year():
    seen = {}

    def transport(url, headers, timeout):
        seen["url"] = url
        return {"results": []}

    query = ResolverQuery(
        raw_reference="Pérez, A. (2020). Long raw citation with many fields.",
        title="Specific parsed title",
        year="2020",
    )
    OpenAlexBackend(rows=3, transport=transport).search(query)

    params = parse_qs(urlparse(seen["url"]).query)
    assert params["search"] == ["Specific parsed title"]
    assert params["filter"] == ["publication_year:2020"]
    assert params["per_page"] == ["3"]


def test_openalex_falls_back_to_raw_reference_when_title_missing():
    seen = {}

    def transport(url, headers, timeout):
        seen["url"] = url
        return {"results": []}

    OpenAlexBackend(transport=transport).search(
        ResolverQuery(raw_reference="A raw unresolved citation")
    )
    params = parse_qs(urlparse(seen["url"]).query)
    assert params["search"] == ["A raw unresolved citation"]


def test_openalex_empty_query_abstains_without_network_call():
    def transport(url, headers, timeout):
        raise AssertionError("transport should not be called")

    backend = OpenAlexBackend(transport=transport)
    assert backend.search(ResolverQuery(raw_reference="")) == ()
