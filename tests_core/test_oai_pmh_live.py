# -*- coding: utf-8 -*-
"""Optional live smoke test against a real OAI-PMH endpoint.

This test is **not** part of the mandatory suite: it needs the network and a
third party's uptime. Run it deliberately:

    BIBLIOREF_TEST_LIVE_OAI=1 pytest tests_core/test_oai_pmh_live.py

Override the endpoint with ``BIBLIOREF_TEST_LIVE_OAI_URL`` / ``..._SET``.

SEDICI is the default because it is a real, large, Spanish-language thesis
repository — it is a *configuration* example, never a special case in the
code. Nothing observed here may be turned into repository-specific logic.
"""
from __future__ import annotations

import itertools
import os

import pytest

from biblioref.repositories import OaiPmhConnector, RepositorySource

LIVE = os.environ.get("BIBLIOREF_TEST_LIVE_OAI") == "1"
BASE_URL = os.environ.get(
    "BIBLIOREF_TEST_LIVE_OAI_URL", "https://sedici.unlp.edu.ar/oai/request"
)

pytestmark = pytest.mark.skipif(
    not LIVE, reason="live OAI-PMH smoke test; set BIBLIOREF_TEST_LIVE_OAI=1 to run"
)


@pytest.fixture(scope="module")
def connector() -> OaiPmhConnector:
    source = RepositorySource(
        id="live-oai",
        name="Live OAI-PMH endpoint",
        protocol="oai-pmh",
        base_url=BASE_URL,
    )
    return OaiPmhConnector(source, timeout=30.0)


def test_identify(connector):
    identity = connector.identify()
    assert identity.protocol_version == "2.0"
    assert identity.repository_name


def test_oai_dc_is_offered(connector):
    prefixes = {fmt.prefix for fmt in connector.list_metadata_formats()}
    assert "oai_dc" in prefixes


def test_a_small_harvest_returns_usable_records(connector):
    records = list(itertools.islice(connector.harvest(), 5))
    assert records
    assert all(record.identifier for record in records)
    assert any(record.title for record in records)
