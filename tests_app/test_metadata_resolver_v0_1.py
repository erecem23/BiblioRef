from copy import deepcopy

from biblioref.resolver import Candidate, MetadataResolver, ResolverQuery
from biblioref.resolver.normalize import normalize_doi


class _Backend:
    def __init__(self, name, candidates=(), error=None):
        self.name = name
        self._candidates = tuple(candidates)
        self._error = error

    def search(self, query):
        if self._error:
            raise self._error
        return self._candidates


def test_query_is_snapshot_and_does_not_mutate_parser_output():
    parsed = {
        "title": "Un estudio social",
        "authors": ["Pérez, Ana"],
        "year": "2019",
        "journal": "Revista de Psicología",
        "doi": "https://doi.org/10.1234/ABC.9",
        "publication_type": "articulo_revista",
        "parser_version": "biblioref-parser-v0.12.5",
        "parser_confidence": 0.9,
    }
    original = deepcopy(parsed)
    query = ResolverQuery.from_parser("Pérez, A. (2019). Un estudio social...", parsed)

    assert parsed == original
    assert query.title == "Un estudio social"
    assert query.authors == ("Pérez, Ana",)
    assert query.year == "2019"
    assert query.doi == "10.1234/abc.9"


def test_doi_normalization_accepts_label_and_url_forms():
    assert normalize_doi("doi: 10.5555/ABC.DEF") == "10.5555/abc.def"
    assert normalize_doi("https://doi.org/10.5555/ABC.DEF") == "10.5555/abc.def"
    assert normalize_doi("not a doi") is None


def test_same_backend_exact_identity_is_deduplicated():
    one = Candidate.from_mapping(
        "crossref",
        {"DOI": "10.1111/example", "title": "Example", "year": 2020, "author": "Smith, J."},
    )
    duplicate = Candidate.from_mapping(
        "crossref",
        {"doi": "https://doi.org/10.1111/EXAMPLE", "title": "Example", "year": 2020, "author": "Smith, J."},
    )
    batch = MetadataResolver([_Backend("crossref", [one, duplicate])]).resolve(
        ResolverQuery(raw_reference="Example")
    )
    assert batch.status == "candidates_found"
    assert len(batch.candidates) == 1


def test_cross_backend_agreement_remains_two_independent_evidence_sources():
    crossref = Candidate.from_mapping(
        "crossref",
        {"doi": "10.1111/example", "title": "Example", "year": 2020, "author": "Smith, J."},
    )
    openalex = Candidate.from_mapping(
        "openalex",
        {"doi": "10.1111/example", "title": "Example", "year": 2020, "author": "Smith, J."},
    )
    batch = MetadataResolver([
        _Backend("crossref", [crossref]),
        _Backend("openalex", [openalex]),
    ]).resolve(ResolverQuery(raw_reference="Example"))

    assert len(batch.candidates) == 2
    assert {x.source for x in batch.candidates} == {"crossref", "openalex"}


def test_backend_failure_is_auditable_and_nonfatal():
    candidate = Candidate.from_mapping(
        "openalex",
        {"title": "Valid candidate", "year": 2021, "author": "García, M."},
    )
    batch = MetadataResolver([
        _Backend("crossref", error=RuntimeError("network down")),
        _Backend("openalex", [candidate]),
    ]).resolve(ResolverQuery(raw_reference="Valid candidate"))

    assert batch.status == "candidates_found"
    assert len(batch.candidates) == 1
    assert len(batch.backend_errors) == 1
    assert batch.backend_errors[0].startswith("crossref:RuntimeError:")


def test_candidate_without_strong_identity_is_not_accidentally_fused():
    a = Candidate.from_mapping("openalex", {"title": "Same title"})
    b = Candidate.from_mapping("openalex", {"title": "Same title"})
    batch = MetadataResolver([_Backend("openalex", [a, b])]).resolve(
        ResolverQuery(raw_reference="Same title")
    )
    assert len(batch.candidates) == 2
