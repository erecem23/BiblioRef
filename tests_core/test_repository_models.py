# -*- coding: utf-8 -*-
"""Contracts for the repository core data models (repository-core-0.1).

These models carry provenance metadata only. Nothing here may influence
extraction, detection, parsing or StyleProfiler.
"""
from __future__ import annotations

import dataclasses
import subprocess
import sys
from pathlib import Path

import pytest

from biblioref.repositories import (
    RepositoryIdentity,
    RepositoryMetadataFormat,
    RepositoryRecord,
    RepositorySet,
    RepositorySource,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_repository_source_holds_a_stable_contract():
    source = RepositorySource(
        id="sedici-unlp",
        name="SEDICI - UNLP",
        protocol="oai-pmh",
        base_url="https://sedici.unlp.edu.ar/oai/request",
    )
    assert source.id == "sedici-unlp"
    assert source.name == "SEDICI - UNLP"
    assert source.protocol == "oai-pmh"
    assert source.base_url == "https://sedici.unlp.edu.ar/oai/request"
    with pytest.raises(dataclasses.FrozenInstanceError):
        source.base_url = "https://other.example.org/oai"  # type: ignore[misc]


@pytest.mark.parametrize(
    "base_url",
    ["ftp://example.org/oai", "file:///etc/passwd", "javascript:alert(1)", "example.org/oai", ""],
)
def test_repository_source_rejects_non_http_base_urls(base_url):
    with pytest.raises(ValueError):
        RepositorySource(id="x", name="X", protocol="oai-pmh", base_url=base_url)


@pytest.mark.parametrize("field", ["id", "name", "protocol"])
def test_repository_source_rejects_empty_identity_fields(field):
    values = {
        "id": "x",
        "name": "X",
        "protocol": "oai-pmh",
        "base_url": "https://example.org/oai/request",
    }
    values[field] = "   "
    with pytest.raises(ValueError):
        RepositorySource(**values)


def test_repository_record_preserves_every_dublin_core_value():
    record = RepositoryRecord(
        repository_id="example",
        identifier="oai:example.org:10915/1001",
        datestamp="2021-04-14T12:00:00Z",
        title="Análisis crítico",
        creators=("Pérez, María Ángeles", "Ñandú, José"),
        dates=("2021-04-14", "2021"),
        types=("info:eu-repo/semantics/doctoralThesis", "Tesis de doctorado"),
        subjects=("Educación superior",),
        languages=("es",),
        descriptions=("Resumen",),
        identifiers=("http://example.org/handle/10915/1001", "https://doi.org/10.35537/1001"),
        rights=("info:eu-repo/semantics/openAccess",),
        sets=("com_10915_1", "col_10915_25"),
        deleted=False,
        raw_metadata={
            "date": ("2021-04-14", "2021"),
            "publisher": ("Universidad de Ejemplo",),
        },
    )
    # Both dates survive: normalisation belongs to a later layer.
    assert record.dates == ("2021-04-14", "2021")
    assert record.raw_metadata["date"] == ("2021-04-14", "2021")
    # Fields outside the common contract are not dropped either.
    assert record.raw_metadata["publisher"] == ("Universidad de Ejemplo",)
    assert record.deleted is False


def test_repository_record_tolerates_missing_metadata():
    record = RepositoryRecord(
        repository_id="example",
        identifier="oai:example.org:10915/1004",
    )
    assert record.datestamp is None
    assert record.title is None
    assert record.creators == ()
    assert record.dates == ()
    assert record.types == ()
    assert record.subjects == ()
    assert record.languages == ()
    assert record.descriptions == ()
    assert record.identifiers == ()
    assert record.rights == ()
    assert record.sets == ()
    assert record.deleted is False
    assert record.raw_metadata == {}


def test_repository_record_preserves_unicode_without_transliteration():
    record = RepositoryRecord(
        repository_id="example",
        identifier="oai:example.org:1",
        title="Educación, ñandúes y 中文",
        creators=("Müller, Jörg",),
    )
    assert record.title == "Educación, ñandúes y 中文"
    assert record.creators == ("Müller, Jörg",)


def test_repository_record_can_be_deleted_without_metadata():
    record = RepositoryRecord(
        repository_id="example",
        identifier="oai:example.org:10915/1002",
        datestamp="2022-07-01T00:00:00Z",
        deleted=True,
    )
    assert record.deleted is True
    assert record.title is None
    assert record.raw_metadata == {}


def test_repository_set_and_metadata_format_contracts():
    thesis_set = RepositorySet(spec="col_10915_25", name="Tesis doctorales")
    assert thesis_set.spec == "col_10915_25"
    assert thesis_set.name == "Tesis doctorales"
    assert thesis_set.description is None

    described = RepositorySet(spec="a", name="A", description="Colección de tesis.")
    assert described.description == "Colección de tesis."

    fmt = RepositoryMetadataFormat(
        prefix="oai_dc",
        schema="http://www.openarchives.org/OAI/2.0/oai_dc.xsd",
        namespace="http://www.openarchives.org/OAI/2.0/oai_dc/",
    )
    assert fmt.prefix == "oai_dc"


def test_repository_identity_allows_optional_fields_to_be_absent():
    identity = RepositoryIdentity(
        repository_name="Repositorio Mínimo",
        base_url="https://example.org/oai/request",
        protocol_version="2.0",
    )
    assert identity.earliest_datestamp is None
    assert identity.deleted_record_policy is None
    assert identity.granularity is None
    assert identity.admin_emails == ()


def test_importing_repositories_does_not_pull_the_bibliographic_pipeline():
    """The repository layer must stay off the extraction/parsing side."""
    probe = (
        "import sys;"
        "import biblioref.repositories;"
        "forbidden = ('biblioref.extraction', 'biblioref.detection', 'biblioref.parsing',"
        " 'biblioref.styleprofiler', 'biblioref.adaptive', 'biblioref.grammar');"
        "leaked = sorted(m for m in sys.modules if m.startswith(forbidden));"
        "print(','.join(leaked))"
    )
    completed = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    assert completed.stdout.strip() == "", completed.stdout
