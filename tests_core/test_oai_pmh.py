# -*- coding: utf-8 -*-
"""OAI-PMH 2.0 protocol client (oai-pmh-0.1).

Every test here is offline: the connector receives an injected transport that
replays stored XML fixtures.
"""
from __future__ import annotations

import socket
from urllib.error import HTTPError, URLError

import pytest

from biblioref.repositories import (
    OaiPmhConnector,
    RepositoryMalformedResponse,
    RepositoryOaiError,
    RepositoryProtocolError,
    RepositoryResponseTooLarge,
    RepositorySource,
    RepositoryTransportError,
)
from tests_support.oai_transport import FakeTransport, fixture_bytes

SOURCE = RepositorySource(
    id="example",
    name="Repositorio de Ejemplo",
    protocol="oai-pmh",
    base_url="https://example.org/oai/request",
)


def connector(*payloads, **kwargs):
    transport = FakeTransport(*payloads)
    return OaiPmhConnector(SOURCE, transport=transport, **kwargs), transport


# --------------------------------------------------------------------------
# Identify
# --------------------------------------------------------------------------

def test_identify_reads_every_declared_field():
    client, transport = connector(fixture_bytes("identify.xml"))
    identity = client.identify()

    assert identity.repository_name == "Repositorio Institucional de Ejemplo"
    assert identity.base_url == "https://example.org/oai/request"
    assert identity.protocol_version == "2.0"
    assert identity.earliest_datestamp == "2003-01-01T00:00:00Z"
    assert identity.deleted_record_policy == "persistent"
    assert identity.granularity == "YYYY-MM-DDThh:mm:ssZ"
    assert identity.admin_emails == ("admin@example.org", "soporte@example.org")
    assert transport.call(0).param("verb") == "Identify"


def test_identify_tolerates_missing_optional_fields():
    client, _ = connector(fixture_bytes("identify_minimal.xml"))
    identity = client.identify()

    assert identity.repository_name == "Repositorio Mínimo"
    assert identity.protocol_version == "2.0"
    assert identity.earliest_datestamp is None
    assert identity.deleted_record_policy is None
    assert identity.granularity is None
    assert identity.admin_emails == ()


def test_requests_carry_timeout_and_user_agent():
    client, transport = connector(
        fixture_bytes("identify.xml"),
        timeout=7.5,
        user_agent="BiblioRef-test/1.0",
    )
    client.identify()
    call = transport.call(0)
    assert call.timeout == 7.5
    assert call.headers["User-Agent"] == "BiblioRef-test/1.0"


# --------------------------------------------------------------------------
# ListMetadataFormats / ListSets
# --------------------------------------------------------------------------

def test_list_metadata_formats():
    client, transport = connector(fixture_bytes("metadata_formats.xml"))
    formats = client.list_metadata_formats()

    assert [f.prefix for f in formats] == ["oai_dc", "mods"]
    assert formats[0].namespace == "http://www.openarchives.org/OAI/2.0/oai_dc/"
    assert transport.call(0).param("verb") == "ListMetadataFormats"


def test_list_sets_keeps_spec_name_and_optional_description():
    client, transport = connector(fixture_bytes("sets.xml"))
    sets = client.list_sets()

    assert [s.spec for s in sets] == ["com_10915_1", "col_10915_25"]
    assert sets[1].name == "Tesis doctorales — Ciencias Sociales"
    assert sets[0].description is None
    assert "Colección de tesis" in (sets[1].description or "")
    assert transport.call(0).param("verb") == "ListSets"


def test_list_sets_follows_its_own_resumption_token():
    """ListSets pages too: a repository with hundreds of collections truncates."""
    client, transport = connector(
        fixture_bytes("sets_page_1.xml"),
        fixture_bytes("sets_page_2.xml"),
    )
    sets = client.list_sets()

    assert [s.spec for s in sets] == ["com_10915_1", "col_10915_25"]
    assert transport.call(1).param("resumptionToken") == "SETS-PAGE-2"
    assert len(transport.calls) == 2


# --------------------------------------------------------------------------
# GetRecord
# --------------------------------------------------------------------------

def test_get_record_ignores_xml_prefix_aliases():
    """The fixture uses z:/q:/w: instead of oai:/oai_dc:/dc:."""
    client, transport = connector(fixture_bytes("record_single.xml"))
    record = client.get_record("oai:example.org:10915/1001")

    assert record.identifier == "oai:example.org:10915/1001"
    assert record.datestamp == "2021-04-14T12:00:00Z"
    assert record.title == "Análisis crítico de la educación superior"
    assert record.creators == ("Pérez, María Ángeles",)
    assert record.languages == ("es",)
    assert record.sets == ("col_10915_25",)
    assert record.repository_id == "example"

    call = transport.call(0)
    assert call.param("verb") == "GetRecord"
    assert call.param("identifier") == "oai:example.org:10915/1001"
    assert call.param("metadataPrefix") == "oai_dc"


def test_get_record_returns_a_deleted_record_without_raising():
    client, _ = connector(fixture_bytes("deleted_record.xml"))
    record = client.get_record("oai:example.org:10915/1002")

    assert record.deleted is True
    assert record.identifier == "oai:example.org:10915/1002"
    assert record.datestamp == "2022-07-01T00:00:00Z"
    assert record.title is None
    assert record.raw_metadata == {}


def test_get_record_accepts_a_record_with_no_metadata_block():
    client, _ = connector(fixture_bytes("empty_metadata.xml"))
    record = client.get_record("oai:example.org:10915/1004")

    assert record.deleted is False
    assert record.title is None
    assert record.creators == ()
    assert record.raw_metadata == {}


def test_get_record_surfaces_the_oai_error_code():
    client, _ = connector(fixture_bytes("oai_error_id.xml"))
    with pytest.raises(RepositoryOaiError) as excinfo:
        client.get_record("oai:example.org:missing")

    assert excinfo.value.code == "idDoesNotExist"
    assert "Unknown identifier" in excinfo.value.message
    assert "idDoesNotExist" in str(excinfo.value)


# --------------------------------------------------------------------------
# ListRecords / harvesting
# --------------------------------------------------------------------------

def test_harvest_translates_set_and_date_filters():
    client, transport = connector(fixture_bytes("records_page_2.xml"))
    list(client.harvest(set_spec="col_10915_25", from_date="2020-01-01", until_date="2024-12-31"))

    call = transport.call(0)
    assert call.param("verb") == "ListRecords"
    assert call.param("metadataPrefix") == "oai_dc"
    assert call.param("set") == "col_10915_25"
    assert call.param("from") == "2020-01-01"
    assert call.param("until") == "2024-12-31"


def test_harvest_keeps_every_dublin_core_value():
    client, _ = connector(fixture_bytes("records_page_1.xml"), fixture_bytes("records_page_2.xml"))
    first = list(client.harvest())[0]

    assert first.title == "Análisis crítico de la educación superior"
    assert first.creators == ("Pérez, María Ángeles", "Ñandú, José")
    assert first.dates == ("2021-04-14", "2021")
    assert first.types == ("info:eu-repo/semantics/doctoralThesis", "Tesis de doctorado")
    assert first.identifiers == (
        "http://sedici.example.org/handle/10915/1001",
        "https://doi.org/10.35537/1001",
    )
    assert first.rights == ("info:eu-repo/semantics/openAccess",)
    assert first.sets == ("com_10915_1", "col_10915_25")
    # Fields outside the common contract stay reachable through raw metadata.
    assert first.raw_metadata["publisher"] == ("Universidad de Ejemplo",)
    assert first.raw_metadata["date"] == ("2021-04-14", "2021")


def test_harvest_follows_the_resumption_token_across_pages():
    client, transport = connector(
        fixture_bytes("records_page_1.xml"),
        fixture_bytes("records_page_2.xml"),
    )
    records = list(client.harvest(set_spec="col_10915_25"))

    identifiers = [r.identifier for r in records]
    assert identifiers == [
        "oai:example.org:10915/1001",
        "oai:example.org:10915/1002",
        "oai:example.org:10915/1003",
    ]
    assert len(identifiers) == len(set(identifiers))
    assert [r.deleted for r in records] == [False, True, False]

    # Page two carries the token only: no incompatible initial parameters.
    second = transport.call(1)
    assert second.param("verb") == "ListRecords"
    assert second.param("resumptionToken") == "TOKEN-PAGE-2"
    assert second.param("metadataPrefix") is None
    assert second.param("set") is None
    assert len(transport.calls) == 2


def test_harvest_stops_on_an_empty_resumption_token():
    client, transport = connector(
        fixture_bytes("records_page_1.xml"),
        fixture_bytes("records_page_2.xml"),
    )
    assert len(list(client.harvest())) == 3
    assert len(transport.calls) == 2


def test_harvest_detects_a_repeated_resumption_token():
    client, _ = connector(
        fixture_bytes("records_page_1.xml"),
        fixture_bytes("records_token_loop.xml"),
    )
    with pytest.raises(RepositoryProtocolError, match="resumptionToken"):
        list(client.harvest())


def test_harvest_respects_the_page_budget():
    """A repository that keeps handing out tokens cannot spin the harvester."""
    client, transport = connector(fixture_bytes("records_page_1.xml"), max_pages=1)
    with pytest.raises(RepositoryProtocolError, match="page"):
        list(client.harvest())
    assert len(transport.calls) == 1


def test_harvest_treats_no_records_match_as_an_empty_result():
    client, _ = connector(fixture_bytes("oai_error.xml"))
    assert list(client.harvest(from_date="2099-01-01")) == []


# --------------------------------------------------------------------------
# Failure modes
# --------------------------------------------------------------------------

def test_malformed_xml_raises_a_typed_error():
    client, _ = connector(fixture_bytes("malformed.xml"))
    with pytest.raises(RepositoryMalformedResponse):
        client.identify()


def test_a_response_without_the_expected_verb_element_is_malformed():
    client, _ = connector(fixture_bytes("sets.xml"))
    with pytest.raises(RepositoryMalformedResponse):
        client.identify()


def test_network_failure_becomes_a_transport_error():
    client, _ = connector(URLError("connection refused"))
    with pytest.raises(RepositoryTransportError):
        client.identify()


def test_timeout_becomes_a_transport_error():
    client, _ = connector(socket.timeout("timed out"))
    with pytest.raises(RepositoryTransportError):
        client.identify()


@pytest.mark.parametrize("status", [404, 500])
def test_http_errors_become_transport_errors_with_the_status(status):
    error = HTTPError("https://example.org/oai/request", status, "boom", {}, None)
    client, _ = connector(error)
    with pytest.raises(RepositoryTransportError) as excinfo:
        client.identify()
    assert excinfo.value.status == status


def test_rate_limiting_is_retried_with_the_delay_the_server_asks_for():
    """Real repositories answer 429 to an impatient harvester."""
    error = HTTPError(
        "https://example.org/oai/request", 429, "slow down", {"Retry-After": "2"}, None
    )
    sleeps = []
    client, transport = connector(
        error, fixture_bytes("identify.xml"), sleeper=sleeps.append
    )
    identity = client.identify()

    assert identity.protocol_version == "2.0"
    assert sleeps == [2.0]
    assert len(transport.calls) == 2


def test_rate_limiting_without_retry_after_backs_off_and_then_gives_up():
    errors = [
        HTTPError("https://example.org/oai/request", 429, "slow down", {}, None)
        for _ in range(4)
    ]
    sleeps = []
    client, transport = connector(*errors, sleeper=sleeps.append, max_retries=2)
    with pytest.raises(RepositoryTransportError) as excinfo:
        client.identify()

    assert excinfo.value.status == 429
    assert len(transport.calls) == 3  # first attempt + two retries
    assert sleeps == sorted(sleeps) and len(sleeps) == 2  # backing off, not hammering


def test_requests_can_be_paced_so_a_repository_is_not_flooded():
    sleeps = []
    client, transport = connector(
        fixture_bytes("records_page_1.xml"),
        fixture_bytes("records_page_2.xml"),
        min_request_interval=0.5,
        sleeper=sleeps.append,
    )
    assert len(list(client.harvest())) == 3
    assert len(transport.calls) == 2
    assert len(sleeps) == 1 and 0 < sleeps[0] <= 0.5


def test_an_injected_transport_is_not_paced():
    """Pacing protects a real endpoint; it must not slow the offline suite."""
    sleeps = []
    client, _ = connector(
        fixture_bytes("records_page_1.xml"),
        fixture_bytes("records_page_2.xml"),
        sleeper=sleeps.append,
    )
    list(client.harvest())
    assert sleeps == []


def test_oversized_responses_are_refused():
    payload = b"<x>" + b"a" * 10_000 + b"</x>"
    client, _ = connector(payload, max_response_bytes=1024)
    with pytest.raises(RepositoryResponseTooLarge):
        client.identify()


def test_connector_refuses_a_source_of_another_protocol():
    other = RepositorySource(
        id="x", name="X", protocol="dspace-rest", base_url="https://example.org/api"
    )
    with pytest.raises(ValueError):
        OaiPmhConnector(other, transport=FakeTransport())
