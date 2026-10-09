from tools.human_gold.openalex_candidates import transform_openalex_snapshot


def test_transform_preserves_pinned_snapshot_query_and_work_type_when_preregistered():
    snapshot = {"results": [{
        "id": "https://openalex.org/W1",
        "type": "dissertation",
        "title": "A thesis",
        "publication_year": 2020,
        "language": "en",
        "open_access": {"oa_status": "green"},
        "primary_location": {
            "pdf_url": "https://repo.example.ca/W1.pdf",
            "landing_page_url": "https://repo.example.ca/items/W1",
            "license": None,
        },
    }]}
    config = {
        "schema_version": "openalex_candidate_transform_v1",
        "document_id_prefix": "hg_openalex_",
        "metadata_source": "OpenAlex Works API metadata snapshot",
        "metadata_source_query": "https://api.openalex.org/works?filter=type:dissertation&sample=200&seed=20260914&per_page=200",
        "metadata_snapshot_sha256": "a" * 64,
        "cache_policy": "local cache only pending redistribution review",
        "country_by_tld": {"ca": "CA"},
    }
    row = transform_openalex_snapshot(snapshot, config)[0]
    assert row["metadata_work_type"] == "dissertation"
    assert row["metadata_source_query"] == config["metadata_source_query"]
    assert row["metadata_snapshot_sha256"] == "a" * 64


def test_legacy_transform_config_remains_byte_shape_compatible_without_provenance_opt_in():
    snapshot = {"results": [{
        "id": "https://openalex.org/W1",
        "type": "dissertation",
        "title": "A thesis",
        "publication_year": 2020,
        "language": "en",
        "open_access": {"oa_status": "green"},
        "primary_location": {
            "pdf_url": "https://repo.example.ca/W1.pdf",
            "landing_page_url": "https://repo.example.ca/items/W1",
            "license": None,
        },
    }]}
    config = {
        "schema_version": "openalex_candidate_transform_v1",
        "document_id_prefix": "hg_openalex_",
        "metadata_source": "OpenAlex Works API metadata snapshot",
        "cache_policy": "local cache only pending redistribution review",
        "country_by_tld": {"ca": "CA"},
    }
    row = transform_openalex_snapshot(snapshot, config)[0]
    assert "metadata_work_type" not in row
    assert "metadata_source_query" not in row
    assert "metadata_snapshot_sha256" not in row
